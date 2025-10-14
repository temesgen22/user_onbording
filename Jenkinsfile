pipeline {
    agent any
    
    environment {
        // Project configuration
        PROJECT_NAME = 'user-onboarding-api'
        PYTHON_VERSION = '3.10'
        
        // Credentials from Jenkins (configure in Jenkins Credentials)
        OKTA_ORG_URL = credentials('okta-org-url')
        OKTA_API_TOKEN = credentials('okta-api-token')
        API_KEY = credentials('api-key')
        
        // Storage configuration
        STORAGE_BACKEND = 'redis'  // or 'memory' for testing
        REDIS_HOST = credentials('redis-host')
        REDIS_PORT = '6379'
        REDIS_DB = '0'
        REDIS_PASSWORD = credentials('redis-password')
        
        // Python virtual environment
        VENV_DIR = '.venv'
    }
    
    options {
        // Keep only last 10 builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        
        // Timeout after 30 minutes
        timeout(time: 30, unit: 'MINUTES')
        
        // Don't allow concurrent builds
        disableConcurrentBuilds()
        
        // Add timestamps to console output
        timestamps()
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
                
                // Display branch and commit info
                script {
                    sh 'git rev-parse --short HEAD > .git/commit-id'
                    env.GIT_COMMIT_ID = readFile('.git/commit-id').trim()
                    echo "Building commit: ${env.GIT_COMMIT_ID}"
                }
            }
        }
        
        stage('Setup Python Environment') {
            steps {
                echo 'Setting up Python virtual environment...'
                sh '''
                    # Create virtual environment
                    python3 -m venv ${VENV_DIR}
                    
                    # Activate and upgrade pip
                    . ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    
                    # Install dependencies
                    pip install -r requirements.txt
                    
                    # Show installed packages
                    pip list
                '''
            }
        }
        
        stage('Lint & Code Quality') {
            steps {
                echo 'Running linters and code quality checks...'
                sh '''
                    . ${VENV_DIR}/bin/activate
                    
                    # Install linting tools (if not in requirements.txt)
                    pip install flake8 pylint black isort mypy || true
                    
                    # Format check with black
                    echo "Checking code formatting with black..."
                    black --check app/ tests/ || echo "Warning: Code formatting issues found"
                    
                    # Import sorting check
                    echo "Checking import sorting with isort..."
                    isort --check-only app/ tests/ || echo "Warning: Import sorting issues found"
                    
                    # Flake8 linting
                    echo "Running flake8..."
                    flake8 app/ tests/ --max-line-length=100 --exclude=venv,.venv || echo "Warning: Flake8 issues found"
                    
                    # Type checking (optional)
                    echo "Running type checking..."
                    mypy app/ --ignore-missing-imports || echo "Warning: Type checking issues found"
                '''
            }
        }
        
        stage('Unit Tests') {
            steps {
                echo 'Running unit tests...'
                sh '''
                    . ${VENV_DIR}/bin/activate
                    
                    # Run pytest with coverage
                    pytest tests/ \
                        --verbose \
                        --junitxml=test-results/junit.xml \
                        --cov=app \
                        --cov-report=xml:coverage.xml \
                        --cov-report=html:coverage_html \
                        --cov-report=term-missing
                '''
            }
            post {
                always {
                    // Publish test results
                    junit 'test-results/junit.xml'
                    
                    // Publish coverage report
                    publishHTML([
                        reportDir: 'coverage_html',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report',
                        keepAll: true,
                        alwaysLinkToLastBuild: true
                    ])
                }
            }
        }
        
        stage('Security Scan') {
            steps {
                echo 'Running security scans...'
                sh '''
                    . ${VENV_DIR}/bin/activate
                    
                    # Install security tools
                    pip install bandit safety || true
                    
                    # Check for known vulnerabilities in dependencies
                    echo "Checking for vulnerable dependencies..."
                    safety check --json > safety-report.json || echo "Warning: Vulnerabilities found"
                    
                    # Run Bandit security linter
                    echo "Running Bandit security scan..."
                    bandit -r app/ -f json -o bandit-report.json || echo "Warning: Security issues found"
                '''
            }
            post {
                always {
                    // Archive security reports
                    archiveArtifacts artifacts: '*-report.json', allowEmptyArchive: true
                }
            }
        }
        
        stage('Build Docker Image') {
            when {
                // Only build Docker image on main/master branch or tags
                anyOf {
                    branch 'main'
                    branch 'master'
                    tag pattern: "v\\d+\\.\\d+\\.\\d+", comparator: "REGEXP"
                }
            }
            steps {
                echo 'Building Docker image...'
                script {
                    // Build Docker image with git commit tag
                    def imageTag = "${env.GIT_COMMIT_ID}"
                    if (env.TAG_NAME) {
                        imageTag = env.TAG_NAME
                    }
                    
                    sh """
                        docker build -t ${PROJECT_NAME}:${imageTag} .
                        docker tag ${PROJECT_NAME}:${imageTag} ${PROJECT_NAME}:latest
                    """
                    
                    env.DOCKER_IMAGE_TAG = imageTag
                }
            }
        }
        
        stage('Integration Tests') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                }
            }
            steps {
                echo 'Running integration tests...'
                sh '''
                    . ${VENV_DIR}/bin/activate
                    
                    # Start the application in background
                    uvicorn app.main:app --host 0.0.0.0 --port 8000 &
                    APP_PID=$!
                    
                    # Wait for app to start
                    sleep 10
                    
                    # Run health check
                    curl -f http://localhost:8000/v1/healthz || (kill $APP_PID && exit 1)
                    
                    # Run integration tests if available
                    pytest tests/integration/ --verbose || true
                    
                    # Clean up
                    kill $APP_PID || true
                '''
            }
        }
        
        stage('Deploy to Staging') {
            when {
                branch 'develop'
            }
            steps {
                echo 'Deploying to staging environment...'
                script {
                    // Example deployment commands - customize for your infrastructure
                    sh '''
                        # Deploy to staging server (example)
                        # ssh user@staging-server "cd /app && git pull && systemctl restart user-onboarding-api"
                        
                        echo "Deploying to staging..."
                        # Add your deployment commands here
                    '''
                }
            }
        }
        
        stage('Deploy to Production') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    tag pattern: "v\\d+\\.\\d+\\.\\d+", comparator: "REGEXP"
                }
            }
            steps {
                // Require manual approval for production
                input message: 'Deploy to Production?', ok: 'Deploy'
                
                echo 'Deploying to production environment...'
                script {
                    sh '''
                        echo "Deploying version ${DOCKER_IMAGE_TAG} to production..."
                        
                        # Example: Deploy using Docker
                        # docker-compose -f docker-compose.prod.yml up -d
                        
                        # Example: Deploy to Kubernetes
                        # kubectl set image deployment/user-onboarding-api api=${PROJECT_NAME}:${DOCKER_IMAGE_TAG}
                        
                        # Example: Deploy to VMs
                        # ssh user@prod-server "cd /app && git pull && systemctl restart user-onboarding-api"
                        
                        # Add your production deployment commands here
                    '''
                }
            }
        }
    }
    
    post {
        always {
            echo 'Cleaning up workspace...'
            
            // Clean up virtual environment
            node {
            cleanWs()// ✅ built-in Jenkins function for safe cleanup
            }
            // Archive important artifacts
            archiveArtifacts artifacts: 'test-results/*.xml, coverage.xml', allowEmptyArchive: true
        }
        
        success {
            echo 'Pipeline completed successfully! ✅'
            
            // Notify on success (example)
            // slackSend color: 'good', message: "Build ${env.BUILD_NUMBER} succeeded for ${env.JOB_NAME}"
            // emailext subject: "Success: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
            //          body: "Build succeeded",
            //          to: "team@example.com"
        }
        
        failure {
            echo 'Pipeline failed! ❌'
            
            // Notify on failure (example)
            // slackSend color: 'danger', message: "Build ${env.BUILD_NUMBER} failed for ${env.JOB_NAME}"
            // emailext subject: "Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
            //          body: "Build failed. Check Jenkins for details.",
            //          to: "team@example.com"
        }
        
        unstable {
            echo 'Pipeline is unstable ⚠️'
        }
    }
}

