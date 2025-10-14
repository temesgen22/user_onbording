"""
Tests for retry mechanism in HR webhook processing.
"""

import pytest
from unittest.mock import patch, AsyncMock
from tenacity import RetryError, stop_after_attempt

from app.api.hr import fetch_okta_data_with_retry, should_retry_exception
from app.schemas import OktaUser
from app.exceptions import (
    OktaAPIError,
    OktaUserNotFoundError,
    OktaConfigurationError
)


class TestShouldRetryException:
    """Test retry decision logic."""
    
    def test_should_not_retry_user_not_found(self):
        """Test that OktaUserNotFoundError is not retried."""
        exception = OktaUserNotFoundError("test@example.com")
        assert should_retry_exception(exception) is False
    
    def test_should_not_retry_configuration_error(self):
        """Test that OktaConfigurationError is not retried."""
        exception = OktaConfigurationError("Config error")
        assert should_retry_exception(exception) is False
    
    def test_should_retry_okta_api_error(self):
        """Test that OktaAPIError is retried."""
        exception = OktaAPIError("API error")
        assert should_retry_exception(exception) is True
    
    def test_should_retry_connection_error(self):
        """Test that ConnectionError is retried."""
        exception = ConnectionError("Network error")
        assert should_retry_exception(exception) is True
    
    def test_should_retry_timeout_error(self):
        """Test that TimeoutError is retried."""
        exception = TimeoutError("Request timeout")
        assert should_retry_exception(exception) is True
    
    def test_should_not_retry_generic_exception(self):
        """Test that generic exceptions are not retried."""
        exception = ValueError("Some error")
        assert should_retry_exception(exception) is False


class TestFetchOktaDataWithRetry:
    """Test retry mechanism for Okta data fetching."""
    
    @pytest.mark.asyncio
    async def test_fetch_success_on_first_attempt(self, sample_okta_user):
        """Test successful fetch on first attempt (no retry needed)."""
        mock_okta_user = OktaUser(**sample_okta_user)
        
        with patch('app.api.hr.load_okta_user_by_email', return_value=mock_okta_user) as mock_load:
            result = await fetch_okta_data_with_retry("test@example.com")
            
            assert result == mock_okta_user
            assert mock_load.call_count == 1
    
    @pytest.mark.asyncio
    async def test_fetch_user_not_found_no_retry(self, sample_okta_user):
        """Test that OktaUserNotFoundError is not retried."""
        mock_load = AsyncMock(side_effect=OktaUserNotFoundError("test@example.com"))
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            with pytest.raises(OktaUserNotFoundError):
                await fetch_okta_data_with_retry("test@example.com")
            
            # Should only be called once (no retry)
            assert mock_load.call_count == 1
    
    @pytest.mark.asyncio
    async def test_fetch_configuration_error_no_retry(self):
        """Test that OktaConfigurationError is not retried."""
        mock_load = AsyncMock(side_effect=OktaConfigurationError("Config error"))
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            with pytest.raises(OktaConfigurationError):
                await fetch_okta_data_with_retry("test@example.com")
            
            # Should only be called once (no retry)
            assert mock_load.call_count == 1
    
    @pytest.mark.asyncio
    async def test_fetch_api_error_with_retry(self, sample_okta_user):
        """Test that OktaAPIError triggers retry and eventually succeeds."""
        mock_okta_user = OktaUser(**sample_okta_user)
        
        # Fail twice, then succeed
        mock_load = AsyncMock(side_effect=[
            OktaAPIError("Temporary error 1"),
            OktaAPIError("Temporary error 2"),
            mock_okta_user
        ])
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            result = await fetch_okta_data_with_retry("test@example.com")
            
            assert result == mock_okta_user
            # Should be called 3 times (2 failures + 1 success)
            assert mock_load.call_count == 3
    
    @pytest.mark.asyncio
    async def test_fetch_api_error_exhausts_retries(self):
        """Test that retry stops after max attempts."""
        # Always fail
        mock_load = AsyncMock(side_effect=OktaAPIError("Persistent error"))
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            # Should raise RetryError after exhausting all attempts
            with pytest.raises(RetryError):
                await fetch_okta_data_with_retry("test@example.com")
            
            # Should be called 3 times (max attempts)
            assert mock_load.call_count == 3
    
    @pytest.mark.asyncio
    async def test_fetch_connection_error_with_retry(self, sample_okta_user):
        """Test that ConnectionError triggers retry."""
        mock_okta_user = OktaUser(**sample_okta_user)
        
        # Fail once with connection error, then succeed
        mock_load = AsyncMock(side_effect=[
            ConnectionError("Network error"),
            mock_okta_user
        ])
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            result = await fetch_okta_data_with_retry("test@example.com")
            
            assert result == mock_okta_user
            assert mock_load.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_timeout_error_with_retry(self, sample_okta_user):
        """Test that TimeoutError triggers retry."""
        mock_okta_user = OktaUser(**sample_okta_user)
        
        # Fail once with timeout, then succeed
        mock_load = AsyncMock(side_effect=[
            TimeoutError("Request timeout"),
            mock_okta_user
        ])
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            result = await fetch_okta_data_with_retry("test@example.com")
            
            assert result == mock_okta_user
            assert mock_load.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_mixed_retryable_errors(self, sample_okta_user):
        """Test retry with different types of retryable errors."""
        mock_okta_user = OktaUser(**sample_okta_user)
        
        # Mix of different retryable errors
        mock_load = AsyncMock(side_effect=[
            OktaAPIError("API error"),
            ConnectionError("Network error"),
            mock_okta_user
        ])
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            result = await fetch_okta_data_with_retry("test@example.com")
            
            assert result == mock_okta_user
            assert mock_load.call_count == 3


class TestRetryConfiguration:
    """Test retry configuration parameters."""
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts(self):
        """Test that retry stops after 3 attempts."""
        mock_load = AsyncMock(side_effect=OktaAPIError("Error"))
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            with pytest.raises(RetryError):
                await fetch_okta_data_with_retry("test@example.com")
            
            # Configured for 3 attempts
            assert mock_load.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff_timing(self, sample_okta_user):
        """Test that retry uses exponential backoff (timing test)."""
        import time
        mock_okta_user = OktaUser(**sample_okta_user)
        
        # Fail twice, then succeed
        mock_load = AsyncMock(side_effect=[
            OktaAPIError("Error 1"),
            OktaAPIError("Error 2"),
            mock_okta_user
        ])
        
        with patch('app.api.hr.load_okta_user_by_email', mock_load):
            start_time = time.time()
            result = await fetch_okta_data_with_retry("test@example.com")
            elapsed_time = time.time() - start_time
            
            # Should wait approximately: 2s + 4s = 6s total
            # Allow some tolerance for test execution
            # Note: In real implementation, backoff is: min=2, multiplier=1, so 2s, 4s, 8s
            assert elapsed_time >= 4  # At least 2s + 2s
            assert elapsed_time < 10  # But not too long
            assert result == mock_okta_user

