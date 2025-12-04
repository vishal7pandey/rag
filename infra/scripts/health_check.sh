#!/bin/bash
set -e

echo "🔍 Checking backend..."
curl -f http://localhost:8000/health || echo "⚠️  Backend not healthy"

echo "🔍 Checking frontend..."
curl -f http://localhost:5173 || echo "⚠️  Frontend not healthy"
