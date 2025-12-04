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
