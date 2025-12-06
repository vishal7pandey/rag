"""Provision Pinecone indexes for the RAG system.

This script follows Story 003 and is intended to be run once per environment
(e.g. dev, staging, prod) to create the dense and sparse indexes if they do
not already exist.

Usage (from repo root):

    uv run python backend/scripts/provision_pinecone.py

Requirements:
- PINECONE_API_KEY set in environment or .env
- Optional env overrides:
  - DENSE_INDEX_NAME (default: rag-dense)
  - SPARSE_INDEX_NAME (default: rag-sparse)
"""

from __future__ import annotations

from pinecone import Pinecone, ServerlessSpec
from pydantic_settings import BaseSettings


class _PineconeProvisionSettings(BaseSettings):
    """Minimal settings loader for Pinecone provisioning.

    Reads from environment variables and .env, so running this script via
    `uv run` will still pick up configuration from the project's .env file.
    """

    PINECONE_API_KEY: str
    DENSE_INDEX_NAME: str = "rag-dense"
    SPARSE_INDEX_NAME: str = "rag-sparse"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def provision_pinecone_indexes() -> None:
    """Create dense and sparse indexes in Pinecone if they do not exist."""

    cfg = _PineconeProvisionSettings()

    pc = Pinecone(api_key=cfg.PINECONE_API_KEY)

    dense_index_name = cfg.DENSE_INDEX_NAME
    sparse_index_name = cfg.SPARSE_INDEX_NAME

    print("🔄 Provisioning Pinecone indexes...")

    existing_names = {idx.name for idx in pc.list_indexes()}

    # Dense index for semantic search
    if dense_index_name not in existing_names:
        print(f"Creating dense index: {dense_index_name}")
        pc.create_index(
            name=dense_index_name,
            dimension=1536,  # text-embedding-3-small
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Dense index '{dense_index_name}' created")
    else:
        print(f"ℹ️  Dense index '{dense_index_name}' already exists")

    # Sparse index for keyword / sparse vectors
    if sparse_index_name not in existing_names:
        print(f"Creating sparse index: {sparse_index_name}")
        pc.create_index(
            name=sparse_index_name,
            dimension=1,  # Sparse vectors have dynamic dimension in v3, 1 is fine
            metric="dotProduct",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Sparse index '{sparse_index_name}' created")
    else:
        print(f"ℹ️  Sparse index '{sparse_index_name}' already exists")

    # Verify
    print("\n📊 Current indexes:")
    for index in pc.list_indexes():
        print(f"  - {index.name}")

    print("\n✅ Pinecone provisioning complete!")


if __name__ == "__main__":
    provision_pinecone_indexes()
