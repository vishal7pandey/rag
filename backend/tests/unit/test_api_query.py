from backend.api.schemas import QueryResponse


def test_query_endpoint_basic_success(client) -> None:
    """POST /api/query returns a helpful answer when no documents are indexed."""

    payload = {"query": "What is the company policy?"}
    response = client.post("/api/query", json=payload)

    assert response.status_code == 200

    data = response.json()
    model = QueryResponse(**data)

    assert "no documents" in model.answer.lower() or "empty" in model.answer.lower()
    assert model.citations == []
    assert model.retrieved_chunks == [] or model.retrieved_chunks is None


def test_query_endpoint_rejects_missing_body(client) -> None:
    """POST /api/query without JSON body triggers validation error (422)."""

    response = client.post("/api/query")

    assert response.status_code == 422
