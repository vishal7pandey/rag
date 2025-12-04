# Repository & Project Skeleton Implementation Guide

**Story**: Day 1–2: Infrastructure & Setup  
**Epic**: Repository & Project Skeleton  
**Approach**: Specification-Driven + Test-Driven Development

---

## Executive Summary

This document provides a complete implementation plan for establishing a monorepo structure for a production-grade RAG (Retrieval-Augmented Generation) application. The approach combines **Specification-Driven Development** (clear contracts and interfaces) with **Test-Driven Development** (verification at each step).

**Acceptance Criteria**:
- ✅ Git repository initialized with clean folder structure (`backend/`, `frontend/`, `infra/`)
- ✅ Basic README with tech stack and run instructions
- ✅ Node/Poetry/virtualenv setup documented with one-liners
- ✅ Verifiable through automated tests

**Time Estimate**: 4-6 hours

---

## Table of Contents

1. [Specification Phase](#1-specification-phase)
2. [Test-Driven Setup](#2-test-driven-setup)
3. [Implementation Steps](#3-implementation-steps)
4. [Verification & Testing](#4-verification--testing)
5. [Documentation Requirements](#5-documentation-requirements)
6. [Success Metrics](#6-success-metrics)

---

## 1. Specification Phase

### 1.1 Repository Structure Specification

rag-application/
├── backend/                    # Python FastAPI application
│   ├── config/                # Configuration management
│   │   └── __init__.py
│   ├── core/                  # Core business logic
│   │   └── __init__.py
│   ├── api/                   # FastAPI endpoints
│   │   └── __init__.py
│   ├── ingestion/             # Document ingestion pipeline
│   │   └── __init__.py
│   ├── data_layer/            # Vector DB & PostgreSQL clients
│   │   └── __init__.py
│   ├── retrieval/             # Search & reranking
│   │   └── __init__.py
│   ├── generation/            # LLM generation layer
│   │   └── __init__.py
│   ├── evaluation/            # RAGAS metrics
│   │   └── __init__.py
│   ├── monitoring/            # Logging & observability
│   │   └── __init__.py
│   ├── tests/                 # Test suite
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── migrations/            # Database migrations
│   ├── requirements.txt       # Production dependencies
│   ├── requirements-dev.txt   # Development dependencies
│   ├── pyproject.toml         # Poetry configuration
│   ├── pytest.ini             # Pytest configuration
│   └── main.py                # Application entry point
│
├── frontend/                  # React TypeScript application
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── Upload/
│   │   │   ├── Chat/
│   │   │   └── Dashboard/
│   │   ├── pages/             # Page components
│   │   │   ├── Ingestion.tsx
│   │   │   ├── Query.tsx
│   │   │   └── Analytics.tsx
│   │   ├── services/          # API clients
│   │   ├── hooks/             # Custom React hooks
│   │   ├── types/             # TypeScript types
│   │   └── App.tsx            # Root component
│   ├── public/                # Static assets
│   ├── tests/                 # Frontend tests
│   ├── package.json           # NPM dependencies
│   ├── tsconfig.json          # TypeScript config
│   ├── vite.config.ts         # Vite bundler config
│   └── .eslintrc.js           # ESLint config
│
├── infra/                     # Infrastructure as Code
│   ├── docker/                # Docker configurations
│   │   ├── backend.Dockerfile
│   │   ├── frontend.Dockerfile
│   │   └── nginx.conf
│   ├── k8s/                   # Kubernetes manifests (future)
│   │   └── .gitkeep
│   ├── terraform/             # Terraform configs (future)
│   │   └── .gitkeep
│   └── scripts/               # Deployment scripts
│       ├── setup_local.sh
│       └── health_check.sh
│
├── docs/                      # Architecture documentation
│   ├── architecture/          # System design docs
│   ├── api/                   # API specifications
│   └── deployment/            # Deployment guides
│
├── .github/                   # GitHub-specific configs
│   ├── workflows/             # CI/CD pipelines
│   │   ├── backend-tests.yml
│   │   ├── frontend-tests.yml
│   │   └── integration.yml
│   └── ISSUE_TEMPLATE/
│
├── docker-compose.yml         # Local development stack
├── .env.example               # Environment template
├── .gitignore                 # Git ignore rules
├── README.md                  # Project documentation
├── CONTRIBUTING.md            # Contribution guidelines
└── LICENSE                    # Project license

**Specification Contract**:
- **Backend**: Python 3.11+, FastAPI framework, Poetry for dependency management
- **Frontend**: Node 18+, React 18+, TypeScript, Vite bundler
- **Infrastructure**: Docker, docker-compose for local dev
- **Testing**: pytest (backend), Vitest (frontend)
- **Versioning**: Git with semantic versioning

---

### 1.2 Technology Stack Specification

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Backend Runtime** | Python | 3.11+ | Core application |
| **Backend Framework** | FastAPI | 0.104+ | API server |
| **Dependency Manager** | Poetry | 1.7+ | Python package management |
| **Frontend Runtime** | Node.js | 18+ | JavaScript runtime |
| **Frontend Framework** | React | 18+ | UI library |
| **Frontend Language** | TypeScript | 5.0+ | Type safety |
| **Frontend Bundler** | Vite | 5.0+ | Fast builds |
| **Package Manager** | npm | 9+ | Node package management |
| **Containerization** | Docker | 24+ | Container runtime |
| **Orchestration** | docker-compose | 2.0+ | Local multi-container |
| **Version Control** | Git | 2.40+ | Source control |
| **Testing (Backend)** | pytest | 7.4+ | Python testing |
| **Testing (Frontend)** | Vitest | 1.0+ | Frontend testing |

---

### 1.3 File Template Specifications

#### Backend `pyproject.toml`
[tool.poetry]
name = "rag-backend"
version = "0.1.0"
description = "RAG Application Backend"
authors = ["Your Team"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
sqlalchemy = "^2.0.0"
alembic = "^1.13.0"
langchain = "^0.1.0"
langchain-openai = "^0.0.2"
pinecone-client = "^3.0.0"
openai = "^1.6.0"
python-multipart = "^0.0.6"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
redis = "^5.0.0"
structlog = "^23.2.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-cov = "^4.1.0"
black = "^23.11.0"
isort = "^5.12.0"
flake8 = "^6.1.0"
mypy = "^1.7.0"
httpx = "^0.25.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

#### Frontend `package.json`
{
  "name": "rag-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:coverage": "vitest --coverage",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "format": "prettier --write \"src/**/*.{ts,tsx,css}\""
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-query": "^3.39.3",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@typescript-eslint/eslint-plugin": "^6.13.0",
    "@typescript-eslint/parser": "^6.13.0",
    "@vitejs/plugin-react": "^4.2.0",
    "eslint": "^8.54.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.4",
    "prettier": "^3.1.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "@vitest/ui": "^1.0.0"
  }
}

#### `docker-compose.yml`
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: infra/docker/backend.Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/ragdb
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: .
      dockerfile: infra/docker/frontend.Dockerfile
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=ragdb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:

---

## 2. Test-Driven Setup

### 2.1 Pre-Implementation Tests

**Test Strategy**: Write validation tests BEFORE creating the structure. Tests should fail initially, then pass after implementation.

#### Test Suite: `tests/test_repository_structure.py`

"""
Repository Structure Validation Tests
Tests run BEFORE implementation to define success criteria
"""
import os
import subprocess
from pathlib import Path


def test_git_repository_initialized():
    """Verify Git repository is properly initialized"""
    assert Path('.git').is_dir(), "Git repository not initialized"
    
    # Check for initial commit
    result = subprocess.run(['git', 'log', '--oneline'], 
                          capture_output=True, text=True)
    assert result.returncode == 0, "Git repository has no commits"
    assert len(result.stdout.strip()) > 0, "No commits found"


def test_backend_structure_exists():
    """Verify backend folder structure"""
    required_dirs = [
        'backend',
        'backend/config',
        'backend/core',
        'backend/api',
        'backend/ingestion',
        'backend/data_layer',
        'backend/retrieval',
        'backend/generation',
        'backend/evaluation',
        'backend/monitoring',
        'backend/tests',
        'backend/tests/unit',
        'backend/tests/integration',
        'backend/migrations',
    ]
    
    for dir_path in required_dirs:
        assert Path(dir_path).is_dir(), f"Missing directory: {dir_path}"


def test_backend_files_exist():
    """Verify backend essential files"""
    required_files = [
        'backend/pyproject.toml',
        'backend/requirements.txt',
        'backend/pytest.ini',
        'backend/main.py',
        'backend/__init__.py',
    ]
    
    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_frontend_structure_exists():
    """Verify frontend folder structure"""
    required_dirs = [
        'frontend',
        'frontend/src',
        'frontend/src/components',
        'frontend/src/pages',
        'frontend/src/services',
        'frontend/src/hooks',
        'frontend/src/types',
        'frontend/public',
        'frontend/tests',
    ]
    
    for dir_path in required_dirs:
        assert Path(dir_path).is_dir(), f"Missing directory: {dir_path}"


def test_frontend_files_exist():
    """Verify frontend essential files"""
    required_files = [
        'frontend/package.json',
        'frontend/tsconfig.json',
        'frontend/vite.config.ts',
        'frontend/src/App.tsx',
    ]
    
    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_infra_structure_exists():
    """Verify infrastructure folder structure"""
    required_dirs = [
        'infra',
        'infra/docker',
        'infra/scripts',
    ]
    
    for dir_path in required_dirs:
        assert Path(dir_path).is_dir(), f"Missing directory: {dir_path}"
    
    required_files = [
        'infra/docker/backend.Dockerfile',
        'infra/docker/frontend.Dockerfile',
    ]
    
    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_root_files_exist():
    """Verify root configuration files"""
    required_files = [
        'docker-compose.yml',
        '.env.example',
        '.gitignore',
        'README.md',
    ]
    
    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_readme_contains_required_sections():
    """Verify README has essential sections"""
    readme = Path('README.md').read_text()
    
    required_sections = [
        '# RAG Application',
        '## Tech Stack',
        '## Quick Start',
        '## Installation',
        '## Running Locally',
    ]
    
    for section in required_sections:
        assert section in readme, f"README missing section: {section}"


def test_backend_poetry_setup():
    """Verify Poetry is properly configured"""
    assert Path('backend/pyproject.toml').exists(), "pyproject.toml missing"
    
    # Test Poetry installation can resolve dependencies
    result = subprocess.run(
        ['poetry', 'check'],
        cwd='backend',
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Poetry check failed: {result.stderr}"


def test_frontend_npm_setup():
    """Verify npm package.json is valid"""
    assert Path('frontend/package.json').exists(), "package.json missing"
    
    # Validate package.json is valid JSON
    import json
    with open('frontend/package.json') as f:
        pkg = json.load(f)
    
    assert 'name' in pkg, "package.json missing 'name'"
    assert 'scripts' in pkg, "package.json missing 'scripts'"
    assert 'dev' in pkg['scripts'], "package.json missing 'dev' script"


def test_docker_compose_valid():
    """Verify docker-compose.yml is valid"""
    result = subprocess.run(
        ['docker-compose', 'config'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"docker-compose.yml invalid: {result.stderr}"


def test_gitignore_comprehensive():
    """Verify .gitignore covers essential patterns"""
    gitignore = Path('.gitignore').read_text()
    
    required_patterns = [
        '__pycache__',
        '*.pyc',
        '.env',
        'node_modules',
        'dist',
        'build',
        '.venv',
        'venv',
        '.DS_Store',
    ]
    
    for pattern in required_patterns:
        assert pattern in gitignore, f".gitignore missing pattern: {pattern}"

---

## 3. Implementation Steps

### 3.1 Initial Setup (30 minutes)

#### Step 1: Initialize Git Repository

# Create project directory
mkdir rag-application
cd rag-application

# Initialize git
git init

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.venv
venv/
ENV/
env/

# Node
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
dist/
build/
.cache/

# Environment
.env
.env.local
.env.*.local

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Testing
.coverage
htmlcov/
.pytest_cache/
coverage/

# Docker
*.pid
*.seed
*.pid.lock
EOF

# Initial commit
git add .gitignore
git commit -m "Initial commit: Add .gitignore"

**Verification Test**:
# Should show initial commit
git log --oneline

---

#### Step 2: Create Backend Structure

# Create backend directories
mkdir -p backend/{config,core,api,ingestion,data_layer,retrieval,generation,evaluation,monitoring}
mkdir -p backend/tests/{unit,integration,e2e}
mkdir -p backend/migrations

# Create __init__.py files
touch backend/__init__.py
find backend -type d -exec touch {}/__init__.py \;

# Create main.py
cat > backend/main.py << 'EOF'
"""
RAG Application Backend
FastAPI Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="RAG Application API",
    description="Production-grade RAG system backend",
    version="0.1.0"
)

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "RAG Application API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Create pyproject.toml (copy from specification above)
# Create requirements.txt
cat > backend/requirements.txt << 'EOF'
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
sqlalchemy>=2.0.0
alembic>=1.13.0
langchain>=0.1.0
langchain-openai>=0.0.2
pinecone-client>=3.0.0
openai>=1.6.0
python-multipart>=0.0.6
redis>=5.0.0
structlog>=23.2.0
EOF

# Create pytest.ini
cat > backend/pytest.ini << 'EOF'
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
EOF

# Commit backend structure
git add backend/
git commit -m "feat: Add backend structure with FastAPI skeleton"

**Verification Test**:
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py  # Should start server on port 8000
curl http://localhost:8000/health  # Should return {"status": "healthy"}

---

#### Step 3: Create Frontend Structure

# Create frontend with Vite
npm create vite@latest frontend -- --template react-ts

cd frontend

# Create additional directories
mkdir -p src/{components,pages,services,hooks,types}
mkdir -p tests

# Create basic App.tsx
cat > src/App.tsx << 'EOF'
import React from 'react';

function App() {
  return (
    <div className="App">
      <h1>RAG Application</h1>
      <p>Welcome to the RAG system interface</p>
    </div>
  );
}

export default App;
EOF

# Update package.json with additional dependencies
npm install react-query axios react-router-dom
npm install -D @vitest/ui vitest

# Commit frontend structure
cd ..
git add frontend/
git commit -m "feat: Add frontend structure with React + TypeScript + Vite"

**Verification Test**:
cd frontend
npm install
npm run dev  # Should start on port 5173
# Visit http://localhost:5173 - should see "RAG Application"

---

#### Step 4: Create Infrastructure

# Create infra directories
mkdir -p infra/{docker,k8s,terraform,scripts}

# Create backend Dockerfile
cat > infra/docker/backend.Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Create frontend Dockerfile
cat > infra/docker/frontend.Dockerfile << 'EOF'
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY frontend/ .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
EOF

# Create docker-compose.yml (copy from specification above)

# Create setup script
cat > infra/scripts/setup_local.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Setting up RAG Application local environment..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker required but not installed"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ docker-compose required"; exit 1; }

# Copy environment template
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file - please configure API keys"
fi

# Build and start services
echo "📦 Building Docker images..."
docker-compose build

echo "🎬 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be healthy..."
sleep 5

# Health checks
echo "🔍 Checking backend..."
curl -f http://localhost:8000/health || echo "⚠️  Backend not ready"

echo "🔍 Checking frontend..."
curl -f http://localhost:5173 || echo "⚠️  Frontend not ready"

echo "✅ Setup complete!"
echo "📝 Backend API: http://localhost:8000"
echo "🖥️  Frontend UI: http://localhost:5173"
echo "📊 API Docs: http://localhost:8000/docs"
EOF

chmod +x infra/scripts/setup_local.sh

# Commit infrastructure
git add infra/
git add docker-compose.yml
git commit -m "feat: Add Docker infrastructure and local setup scripts"

---

#### Step 5: Create Documentation

# Create docs structure
mkdir -p docs/{architecture,api,deployment}

# Create comprehensive README
cat > README.md << 'EOF'
# RAG Application

Production-grade Retrieval-Augmented Generation (RAG) system with full observability and modern architecture.

## Tech Stack

### Backend
- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **Dependency Management**: Poetry
- **Database**: PostgreSQL 16
- **Vector Database**: Pinecone
- **Cache**: Redis
- **LLM**: OpenAI GPT-4o
- **Embeddings**: OpenAI text-embedding-3-small
- **Observability**: LangSmith, Prometheus, Grafana

### Frontend
- **Runtime**: Node.js 18+
- **Framework**: React 18+ with TypeScript
- **Bundler**: Vite
- **State Management**: React Query
- **Routing**: React Router

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: docker-compose (local), Kubernetes (production)
- **CI/CD**: GitHub Actions

## Quick Start

### Prerequisites

- Docker 24+ and docker-compose 2.0+
- Git 2.40+
- (Optional) Python 3.11+ and Node 18+ for local development

### One-Command Setup

# Clone repository
git clone <repository-url>
cd rag-application

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys:
# - OPENAI_API_KEY
# - PINECONE_API_KEY
# - LANGSMITH_API_KEY

# Run setup script
./infra/scripts/setup_local.sh

**Services will be available at:**
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Frontend UI: http://localhost:5173
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Installation

### Backend Setup (Python)

cd backend

# Option 1: Using Poetry (recommended)
poetry install
poetry shell
python main.py

# Option 2: Using pip + virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py

### Frontend Setup (Node)

cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

## Running Locally

### Using Docker Compose (Recommended)

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

### Manual Development Mode

**Terminal 1 - Backend**:
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

**Terminal 2 - Frontend**:
cd frontend
npm run dev

**Terminal 3 - Services**:
docker-compose up postgres redis

## Environment Configuration

Copy `.env.example` to `.env` and configure:

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...

# Pinecone
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ragdb

# Redis
REDIS_URL=redis://localhost:6379

# LangSmith
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=rag-system

# Security
JWT_SECRET=your-secret-key

## Project Structure

rag-application/
├── backend/          # FastAPI application
├── frontend/         # React TypeScript app
├── infra/            # Infrastructure configs
├── docs/             # Documentation
└── docker-compose.yml

## Development Workflow

1. **Create feature branch**: `git checkout -b feature/your-feature`
2. **Make changes** in `backend/` or `frontend/`
3. **Run tests**: 
   - Backend: `cd backend && pytest`
   - Frontend: `cd frontend && npm test`
4. **Commit**: `git commit -m "feat: description"`
5. **Push**: `git push origin feature/your-feature`
6. **Create PR** on GitHub

## Testing

### Backend Tests
cd backend
pytest                          # Run all tests
pytest tests/unit              # Unit tests only
pytest --cov=. --cov-report=html  # With coverage

### Frontend Tests
cd frontend
npm test                        # Run tests
npm run test:coverage          # With coverage

## API Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Monitoring

- **LangSmith**: Trace debugging at https://smith.langchain.com
- **Logs**: `docker-compose logs -f backend`
- **Metrics**: Prometheus (coming soon)
- **Dashboards**: Grafana (coming soon)

## Troubleshooting

### Backend won't start
# Check logs
docker-compose logs backend

# Rebuild container
docker-compose up -d --build backend

# Check database connection
docker-compose exec backend python -c "from config import settings; print(settings.DATABASE_URL)"

### Frontend won't start
# Clear node_modules
rm -rf frontend/node_modules
npm install

# Check Vite config
cd frontend && npm run dev -- --debug

### Database issues
# Reset database
docker-compose down -v
docker-compose up -d postgres

# Run migrations
docker-compose exec backend alembic upgrade head

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[MIT License](LICENSE)

---

**Built with ❤️ for production-grade RAG systems**
EOF

# Create .env.example
cat > .env.example << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_ORG_ID=org-your-org-id-here

# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-east-1-aws

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@db:5432/ragdb

# Redis Configuration
REDIS_URL=redis://redis:6379

# LangSmith Configuration
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=rag-system

# Security
JWT_SECRET=your-secret-key-change-in-production

# Application Settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
EOF

# Commit documentation
git add README.md .env.example docs/
git commit -m "docs: Add comprehensive README and environment template"

---

## 4. Verification & Testing

### 4.1 Run Structure Validation Tests

# Install pytest for structure tests
pip install pytest

# Run all validation tests
pytest tests/test_repository_structure.py -v

# Expected output:
# ✅ test_git_repository_initialized PASSED
# ✅ test_backend_structure_exists PASSED
# ✅ test_backend_files_exist PASSED
# ✅ test_frontend_structure_exists PASSED
# ✅ test_frontend_files_exist PASSED
# ✅ test_infra_structure_exists PASSED
# ✅ test_root_files_exist PASSED
# ✅ test_readme_contains_required_sections PASSED
# ✅ test_backend_poetry_setup PASSED
# ✅ test_frontend_npm_setup PASSED
# ✅ test_docker_compose_valid PASSED
# ✅ test_gitignore_comprehensive PASSED

### 4.2 Integration Verification

# Test complete stack startup
./infra/scripts/setup_local.sh

# Verify services
docker-compose ps  # All should show "Up"

# Test backend health
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "0.1.0"}

# Test frontend
curl http://localhost:5173
# Expected: HTML with "RAG Application"

# Test API docs
open http://localhost:8000/docs  # Should show Swagger UI

# Cleanup
docker-compose down

### 4.3 Dependency Installation Tests

# Test backend dependencies
cd backend
poetry install  # Should complete without errors
poetry run pytest --version  # Should show pytest version

# Test frontend dependencies
cd ../frontend
npm install  # Should complete without errors
npm run build  # Should build successfully

---

## 5. Documentation Requirements

### 5.1 README Checklist

- [x] Project title and description
- [x] Tech stack table (backend, frontend, infrastructure)
- [x] Quick start one-liner
- [x] Prerequisites list
- [x] Installation instructions (Poetry + pip, npm)
- [x] Running locally (Docker + manual)
- [x] Environment configuration
- [x] Project structure diagram
- [x] Development workflow
- [x] Testing commands
- [x] API documentation links
- [x] Troubleshooting section
- [x] Contributing guidelines link
- [x] License

### 5.2 Additional Documentation Files

Create these supporting documents:

**CONTRIBUTING.md**:
# Contributing to RAG Application

## Development Setup

1. Fork the repository
2. Clone your fork
3. Create feature branch
4. Make changes
5. Run tests
6. Submit PR

## Code Style

- **Backend**: Black (line length 100), isort, flake8
- **Frontend**: Prettier, ESLint
- **Commits**: Conventional Commits format

## Testing Requirements

- All new features must include tests
- Maintain >80% code coverage
- All tests must pass before PR merge

## PR Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure CI passes
4. Request review from maintainers

---

## 6. Success Metrics

### 6.1 Acceptance Criteria Verification

| Criterion | Verification Method | Status |
|-----------|-------------------|---------|
| Git repo initialized | `git log` shows commits | ✅ |
| Clean folder structure | All dirs in spec exist | ✅ |
| Backend structure | `backend/` dirs present | ✅ |
| Frontend structure | `frontend/src/` dirs present | ✅ |
| Infra structure | `infra/docker/` files exist | ✅ |
| README with tech stack | README contains "Tech Stack" section | ✅ |
| README with run instructions | README contains "Quick Start" | ✅ |
| Poetry setup | `poetry check` passes | ✅ |
| npm setup | `npm install` succeeds | ✅ |
| Docker setup | `docker-compose up` works | ✅ |
| All tests pass | `pytest tests/` all green | ✅ |

### 6.2 Quality Metrics

- **Test Coverage**: 100% of structure validation tests passing
- **Documentation Coverage**: All required sections in README
- **Setup Time**: < 5 minutes from clone to running
- **Build Success**: All Docker images build without errors

---

## Appendix A: One-Liner Commands Reference

### Backend (Python + Poetry)

# Setup with Poetry
cd backend && poetry install && poetry shell

# Setup with pip
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Run backend
uvicorn main:app --reload

# Run tests
pytest

### Frontend (Node + npm)

# Setup
cd frontend && npm install

# Run dev server
npm run dev

# Run tests
npm test

### Full Stack (Docker)

# Setup and run everything
./infra/scripts/setup_local.sh

# Or manually
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

---

## Appendix B: Troubleshooting Guide

### Issue: Poetry not found

**Solution**:
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

### Issue: Docker-compose command not found

**Solution**:
# Install Docker Desktop (includes compose)
# Or install compose plugin
sudo apt install docker-compose-plugin

### Issue: Port already in use

**Solution**:
# Find process using port 8000
lsof -i :8000
# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml

### Issue: npm install fails with permission errors

**Solution**:
# Fix npm permissions
sudo chown -R $USER ~/.npm
sudo chown -R $USER /usr/local/lib/node_modules

---

## Summary

This implementation guide provides:

1. **Complete specifications** for repository structure, tech stack, and file templates
2. **Test-driven approach** with validation tests that define success criteria
3. **Step-by-step implementation** with copy-paste commands
4. **Verification procedures** to ensure everything works
5. **Comprehensive documentation** that meets all acceptance criteria
6. **Troubleshooting guidance** for common issues

**Time Breakdown**:
- Git initialization: 15 min
- Backend structure: 45 min
- Frontend structure: 45 min
- Infrastructure: 45 min
- Documentation: 30 min
- Testing & verification: 30 min
- **Total**: ~3.5 hours (well within 4-6 hour estimate)

**Next Steps**:
After completing this setup, proceed to Day 3-4: Basic Ingestion Pipeline implementation.

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-04  
**Author**: Development Team
