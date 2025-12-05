"""
Repository Structure Validation Tests
Tests run BEFORE implementation to define success criteria
"""

import json
import subprocess
from pathlib import Path


def test_git_repository_initialized():
    """Verify Git repository is properly initialized"""
    assert Path(".git").is_dir(), "Git repository not initialized"

    # Check for initial commit
    result = subprocess.run(
        ["git", "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Git repository has no commits"
    assert len(result.stdout.strip()) > 0, "No commits found"


def test_backend_structure_exists():
    """Verify backend folder structure"""
    required_dirs = [
        "backend",
        "backend/config",
        "backend/core",
        "backend/api",
        "backend/ingestion",
        "backend/data_layer",
        "backend/retrieval",
        "backend/generation",
        "backend/evaluation",
        "backend/monitoring",
        "backend/tests",
        "backend/tests/unit",
        "backend/tests/integration",
        "backend/migrations",
    ]

    for dir_path in required_dirs:
        assert Path(dir_path).is_dir(), f"Missing directory: {dir_path}"


def test_backend_files_exist():
    """Verify backend essential files"""
    required_files = [
        "pyproject.toml",
        "pytest.ini",
        "backend/requirements.txt",
        "backend/main.py",
        "backend/__init__.py",
    ]

    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_frontend_structure_exists():
    """Verify frontend folder structure"""
    required_dirs = [
        "frontend",
        "frontend/src",
        "frontend/src/components",
        "frontend/src/pages",
        "frontend/src/services",
        "frontend/src/hooks",
        "frontend/src/types",
        "frontend/public",
        "frontend/tests",
    ]

    for dir_path in required_dirs:
        assert Path(dir_path).is_dir(), f"Missing directory: {dir_path}"


def test_frontend_files_exist():
    """Verify frontend essential files"""
    required_files = [
        "frontend/package.json",
        "frontend/tsconfig.json",
        "frontend/vite.config.ts",
        "frontend/src/App.tsx",
    ]

    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_infra_structure_exists():
    """Verify infrastructure folder structure"""
    required_dirs = [
        "infra",
        "infra/docker",
        "infra/scripts",
    ]

    for dir_path in required_dirs:
        assert Path(dir_path).is_dir(), f"Missing directory: {dir_path}"

    required_files = [
        "infra/docker/backend.Dockerfile",
        "infra/docker/frontend.Dockerfile",
    ]

    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_root_files_exist():
    """Verify root configuration files"""
    required_files = [
        "docker-compose.yml",
        ".env.example",
        ".gitignore",
        "README.md",
    ]

    for file_path in required_files:
        assert Path(file_path).is_file(), f"Missing file: {file_path}"


def test_readme_contains_required_sections():
    """Verify README has essential sections"""
    readme = Path("README.md").read_text()

    required_sections = [
        "# RAG Application",
        "## Tech Stack",
        "## Quick Start",
        "## Installation",
        "## Running Locally",
    ]

    for section in required_sections:
        assert section in readme, f"README missing section: {section}"


def test_backend_uv_setup():
    """Verify uv is available and pyproject exists at repo root"""
    assert Path("pyproject.toml").exists(), "pyproject.toml missing at repo root"

    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"uv not available: {result.stderr}"


def test_frontend_npm_setup():
    """Verify npm package.json is valid"""
    assert Path("frontend/package.json").exists(), "package.json missing"

    with open("frontend/package.json") as f:
        pkg = json.load(f)

    assert "name" in pkg, "package.json missing 'name'"
    assert "scripts" in pkg, "package.json missing 'scripts'"
    assert "dev" in pkg["scripts"], "package.json missing 'dev' script"


def test_docker_compose_valid():
    """Verify docker-compose.yml is valid"""
    result = subprocess.run(
        ["docker-compose", "config"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"docker-compose.yml invalid: {result.stderr}"


def test_gitignore_comprehensive():
    """Verify .gitignore covers essential patterns"""
    gitignore = Path(".gitignore").read_text()

    required_patterns = [
        "__pycache__",
        "*.pyc",
        ".env",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        ".DS_Store",
    ]

    for pattern in required_patterns:
        assert pattern in gitignore, f".gitignore missing pattern: {pattern}"
