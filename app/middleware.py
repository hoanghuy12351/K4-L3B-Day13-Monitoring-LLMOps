from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars  #
import re

REQUEST_ID_PATTERN = re.compile(r"^req-[0-9a-f]{8}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # hàm
        clear_contextvars()

        incoming_id = request.headers.get("x-request-id", "").strip()
        if REQUEST_ID_PATTERN.fullmatch(incoming_id):
            correlation_id = incoming_id.lower()
        else:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        bind_contextvars(
            correlation_id=correlation_id
        )  # gắn correlation_id vào contextvars để có thể truy cập trong các phần khác của ứng dụng
        request.state.correlation_id = correlation_id  # state là một đối tượng lưu trữ dữ liệu liên quan đến request, có thể truy cập trong suốt vòng đời của request

        start = time.perf_counter()
        response = await call_next(
            request
        )  # gọi middleware tiếp theo trong chuỗi xử lý request
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"  # el

        return response
