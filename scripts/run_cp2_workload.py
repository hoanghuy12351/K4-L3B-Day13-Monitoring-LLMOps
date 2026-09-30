"""Generate CP2 lab traces through the real FastAPI request path."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio


SAFE_QUESTIONS = [
    "Explain how metrics, logs, and traces support incident investigation.",
    "What does latency P95 mean for a chat API?",
    "How can a correlation ID connect logs to traces?",
    "Summarize the monitoring workflow for an AI application.",
    "Why should a generation observation include token usage?",
    "How do prompt versions help with rollback?",
    "What is an error budget in an SLO?",
    "How can retrieval latency affect the total response time?",
    "Which dashboard panels help investigate high cost?",
    "What should an alert runbook check first?",
]


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Tạo traces CP2 trong project Langfuse cá nhân")
    parser.add_argument("--label", choices=["baseline", "candidate", "production"], default="production")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--same-input", action="store_true", help="So sánh hai prompt version với cùng input an toàn")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit phải >= 1")

    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        parser.error("Thiếu Langfuse keys trong .env; không thể tạo trace Cloud hợp lệ")
    os.environ["LANGFUSE_PROMPT_LABEL"] = args.label

    from app.main import app
    from langfuse import get_client

    if args.same_input:
        payloads = [{
            "user_id": "cp2-learner",
            "feature": "qa",
            "session_id": "cp2-prompt-comparison",
            "message": "Explain how metrics, logs, and traces support incident investigation.",
        }] * args.limit
    else:
        payloads = [
            {
                "user_id": "cp2-learner",
                "feature": "qa",
                "session_id": "cp2-safe-workload",
                "message": SAFE_QUESTIONS[index % len(SAFE_QUESTIONS)],
            }
            for index in range(args.limit)
        ]

    with TestClient(app) as client:
        for index, payload in enumerate(payloads, start=1):
            response = client.post("/chat", json=payload)
            if response.status_code != 200:
                print(f"Request {index} thất bại: HTTP {response.status_code}")
                return 1
            print(f"{index}/{len(payloads)} {args.label}: {response.json()['correlation_id']}")

    get_client().flush()
    print(f"Đã gửi {len(payloads)} request với label {args.label}; kiểm tra traces trên Langfuse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
