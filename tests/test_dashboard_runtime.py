from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import dashboard
from app.main import app


def test_dashboard_uses_real_log_events_and_includes_successful_retrieval(tmp_path, monkeypatch):
    log_dir = tmp_path / "data"
    log_dir.mkdir()
    stamp = "2026-01-01T11:59:00+00:00"
    rows = [
        {"ts": stamp, "event": "request_received"},
        {"ts": stamp, "event": "request_received"},
        {"ts": stamp, "event": "request_received"},
        {"ts": stamp, "event": "response_sent", "latency_ms": 100, "ttft_ms": 30,
         "cost_usd": 0.01, "tokens_in": 10, "tokens_out": 20,
         "quality_score": 0.8, "tool_name": "retrieval", "tool_success": True},
        {"ts": stamp, "event": "response_sent", "latency_ms": 300, "ttft_ms": 50,
         "cost_usd": 0.02, "tokens_in": 15, "tokens_out": 25,
         "quality_score": 0.6, "tool_name": "retrieval", "tool_success": True},
        {"ts": stamp, "event": "request_failed", "error_type": "RuntimeError",
         "tool_name": "retrieval", "tool_success": False},
    ]
    (log_dir / "logs.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(dashboard, "REPO_ROOT", tmp_path)

    result = dashboard.dashboard_snapshot(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    panels = result["panels"]
    assert panels["traffic"]["count"] == 3
    assert panels["latency"]["p50"] == 200
    assert panels["latency"]["p95"] == 290
    assert panels["latency"]["ttft_p95"] == 49
    assert panels["errors"]["error_rate_pct"] == 33.33
    assert panels["errors"]["retrieval_success_rate_pct"] == 66.67
    assert panels["errors"]["by_type"] == {"RuntimeError": 1}
    assert panels["cost"]["total_usd"] == 0.03
    assert panels["tokens"]["input_total"] == 25
    assert panels["tokens"]["output_total"] == 45
    assert panels["quality"]["mean"] == 0.7


def test_dashboard_page_exposes_six_panels():
    response = TestClient(app).get("/dashboard")
    assert response.status_code == 200
    assert response.text.count('class="card"') == 6
    assert "/dashboard/data" in response.text
