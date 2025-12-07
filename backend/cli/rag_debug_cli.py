from __future__ import annotations

import json
from typing import Optional

import httpx
import typer

app = typer.Typer(help="RAG debug CLI for inspecting evaluation artifacts (Story 016)")


@app.command("get-artifacts")
def get_artifacts(
    trace_id: str = typer.Argument(..., help="Trace ID to fetch artifacts for"),
    base_url: str = typer.Option(
        "http://localhost:8000",
        "--base-url",
        help="Base URL of the RAG backend (e.g. http://localhost:8000)",
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Optional bearer token for /api/debug/artifacts (DEBUG_ARTIFACTS_TOKEN)",
    ),
) -> None:
    """Fetch and print debug artifacts for a given trace ID."""

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{base_url.rstrip('/')}/api/debug/artifacts"

    try:
        resp = httpx.get(
            url, params={"trace_id": trace_id}, headers=headers, timeout=30.0
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Request failed: {exc}", err=True)
        raise typer.Exit(code=1)

    if resp.status_code != 200:
        typer.echo(f"Error {resp.status_code}: {resp.text}", err=True)
        raise typer.Exit(code=1)

    data = resp.json()
    typer.echo(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover - manual CLI entrypoint
    app()
