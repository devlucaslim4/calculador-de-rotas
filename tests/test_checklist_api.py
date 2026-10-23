from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from checklist_api import (
    ChecklistApiClient,
    ChecklistAuthenticationError,
    ChecklistIncompleteError,
)


@dataclass
class FakeResponse:
    payload: object
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        if not self.responses:
            raise AssertionError("A consulta fez mais chamadas que o esperado.")
        return self.responses.pop(0)


def page(data, current=1, has_more=False):
    return FakeResponse({"data": data, "meta": {"currentPage": current, "hasMore": has_more}})


def make_client(responses):
    session = FakeSession(responses)
    client = ChecklistApiClient(
        "segredo-de-teste",
        session=session,
        sleep=lambda _: None,
        min_interval_seconds=0,
    )
    return client, session


def evaluation(identifier, concluded, *, updated=None, checklist_id=10, status=6, deleted_at=None):
    return {
        "evaluationId": identifier,
        "checklistId": checklist_id,
        "status": status,
        "concludedAt": concluded,
        "updatedAt": updated or concluded,
        "deletedAt": deleted_at,
    }


def test_reads_every_page_and_requires_has_more_confirmation():
    client, session = make_client([page([{"id": 1}], has_more=True), page([{"id": 2}], current=2)])
    assert client.iter_paginated("/v1/example") == [{"id": 1}, {"id": 2}]
    assert [call["params"]["page"] for call in session.calls] == [1, 2]
    assert all(call["params"]["limit"] == 1000 for call in session.calls)


def test_rejects_response_without_pagination_completion_marker():
    client, _ = make_client([FakeResponse({"data": []})])
    with pytest.raises(ChecklistIncompleteError, match="data/meta"):
        client.iter_paginated("/v1/evaluations")


def test_authentication_failure_has_clear_error():
    client, _ = make_client([FakeResponse({}, status_code=401)])
    with pytest.raises(ChecklistAuthenticationError, match="credencial"):
        client.iter_paginated("/v1/evaluations")


def test_current_month_uses_completion_filter_and_deduplicates_latest_record():
    rows = [
        evaluation(1, "2026-10-01T03:00:00+00:00", updated="2026-10-02T10:00:00+00:00"),
        evaluation(1, "2026-10-01T03:00:00+00:00", updated="2026-10-03T10:00:00+00:00"),
        evaluation(2, "2026-11-01T02:59:59+00:00"),
        evaluation(3, "2026-10-01T02:59:59+00:00"),
        evaluation(4, "2026-10-15T12:00:00+00:00", checklist_id=99),
        evaluation(5, "2026-10-15T12:00:00+00:00", status=2),
    ]
    client, session = make_client([page(rows)])
    result, duplicates = client.list_evaluations(10, 2026, 10)
    assert [row["evaluationId"] for row in result] == [1, 2]
    assert result[0]["updatedAt"] == "2026-10-03T10:00:00+00:00"
    assert duplicates == 1
    params = session.calls[0]["params"]
    assert params["status"] == 6
    assert params["checklistId"] == 10
    assert params["concludedAt[gte]"].startswith("2026-10-01T00:00:00-03:00")
    assert params["concludedAt[lte]"] == "2026-10-31T23:59:59-03:00"


def test_historical_month_filters_by_local_completion_date():
    rows = [
        evaluation(7, "2025-02-01T02:59:59+00:00"),
        evaluation(8, "2025-02-01T03:00:00+00:00"),
    ]
    client, _ = make_client([page(rows)])
    result, _ = client.list_evaluations(10, 2025, 2)
    assert [row["evaluationId"] for row in result] == [8]


def test_per_evaluation_results_never_accept_partial_data():
    client, _ = make_client([page([{"resultId": 1}], has_more=True)])
    with pytest.raises(ChecklistIncompleteError, match="Nenhum arquivo parcial"):
        client.get_evaluation_results(123)


def test_aggregate_results_are_fetched_once_and_grouped_by_evaluation():
    rows = [
        {"resultId": 1, "evaluationId": 10},
        {"resultId": 2, "evaluationId": 20},
        {"resultId": 3, "evaluationId": 999},
    ]
    client, session = make_client([page(rows)])

    grouped = client.list_evaluation_results(77, 2026, 10, {10, 20})

    assert [row["resultId"] for row in grouped[10]] == [1]
    assert [row["resultId"] for row in grouped[20]] == [2]
    assert len(session.calls) == 1
    assert session.calls[0]["url"].endswith("/v3/evaluations/results")
    assert session.calls[0]["params"]["checklistId"] == 77
    assert session.calls[0]["params"]["limit"] == 1000
