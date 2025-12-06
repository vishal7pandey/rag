# RAG Application


Production-grade Retrieval-Augmented Generation (RAG) system with full observability and modern architecture.


## Tech Stack


### Backend
- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **Dependency Management**: uv
- **Database**: PostgreSQL 16
- **Vector Database**: Pinecone
- **Cache**: Redis
- **LLM**: OpenAI gpt-5-nano
- **Embeddings**: OpenAI text-embedding-3-small (1536-dim)
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


```bash
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
```


**Services will be available at:**
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Frontend UI: http://localhost:5173
- PostgreSQL: localhost:5432
- Redis: localhost:6379


## Installation


### Backend Setup (Python)


```bash
cd rag-application  # If you cloned into a different directory, cd there instead


# Option 1: Using uv (recommended)
# Install dependencies defined in pyproject.toml at the repo root
uv sync

# Run the backend API
uv run python backend/main.py


# Option 2: Using pip + virtualenv
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```


### Frontend Setup (Node)


```bash
cd frontend


# Install dependencies
npm install


# Start development server
npm run dev


# Build for production
npm run build
```


## Running Locally


### Using Docker Compose (Recommended)


```bash
# Start all services
docker-compose up -d


# View logs
docker-compose logs -f


# Stop services
docker-compose down


# Rebuild after code changes
docker-compose up -d --build
```


### Manual Development Mode


**Terminal 1 - Backend**:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```


**Terminal 2 - Frontend**:
```bash
cd frontend
npm run dev
```


**Terminal 3 - Services**:
```bash
docker-compose up postgres redis
```


## Environment Configuration


Copy `.env.example`  to `.env` and configure:


```bash
# OpenAI Provider
OPENAI_API_KEY=sk-your-api-key
OPENAI_ORG_ID=org-your-org-id   # optional

# Embedding Configuration
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_BATCH_SIZE=100

# Generation Configuration
OPENAI_GENERATION_MODEL=gpt-5-nano
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_OUTPUT_TOKENS=1000


# Pinecone
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-east-1-aws
DENSE_INDEX_NAME=rag-dense
SPARSE_INDEX_NAME=rag-sparse


# Database (local Docker Compose)
DATABASE_URL=postgresql://postgres:postgres@db:5432/ragdb


# Redis
REDIS_URL=redis://redis:6379


# LangSmith (optional)
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=rag-system


# Security
JWT_SECRET=your-secret-key-change-in-production


# Application
ENVIRONMENT=dev  # dev | staging | prod
```


## Project Structure


```text
rag-application/
├── backend/          # FastAPI application
├── frontend/         # React TypeScript app
├── infra/            # Infrastructure configs
├── docs/             # Documentation
└── docker-compose.yml
```


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
```bash
cd backend
pytest                          # Run all tests
pytest tests/unit               # Unit tests only
pytest --cov=. --cov-report=html  # With coverage
```


### Frontend Tests
```bash
cd frontend
npm test                        # Run tests
npm run test:coverage           # With coverage
```


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
```bash
# Check logs
docker-compose logs backend


# Rebuild container
docker-compose up -d --build backend


# Check database connection
docker-compose exec backend python -c "from config import settings; print(settings.DATABASE_URL)"
```


### Frontend won't start
```bash
# Clear node_modules
rm -rf frontend/node_modules
npm install


# Check Vite config
cd frontend && npm run dev -- --debug
```


### Database issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres


# Run migrations
docker-compose exec backend alembic upgrade head
```


## Contributing


See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.


## License


[MIT License](LICENSE)


---


**Built with ❤️ for production-grade RAG systems**
