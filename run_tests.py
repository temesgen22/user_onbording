#!/usr/bin/env python3
"""
Test runner script for the User Onboarding Integration API.
This script provides various options for running tests.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    return result.returncode == 0


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run tests for User Onboarding Integration API")
    parser.add_argument(
        "--type", 
        choices=["all", "unit", "integration", "schemas", "api", "okta", "store"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick tests only (skip slow tests)"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
    
    # Add quick mode
    if args.quick:
        cmd.extend(["-m", "not slow"])
    
    # Determine test path based on type
    test_paths = {
        "all": ["tests/"],
        "unit": ["tests/", "-m", "unit"],
        "integration": ["tests/", "-m", "integration"],
        "schemas": ["tests/test_schemas.py"],
        "api": ["tests/test_api.py"],
        "okta": ["tests/test_okta_loader.py"],
        "store": ["tests/test_store.py"]
    }
    
    cmd.extend(test_paths[args.type])
    
    # Run the tests
    success = run_command(cmd, f"Running {args.type} tests")
    
    if success:
        print(f"\nSUCCESS: All {args.type} tests passed!")
        if args.coverage:
            print("\nCoverage report generated in htmlcov/index.html")
    else:
        print(f"\nFAILED: Some {args.type} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
