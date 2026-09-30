# Dựng và kiểm tra dashboard

[`../config/dashboard.yaml`](../config/dashboard.yaml) là contract chấm điểm, không phụ thuộc việc bạn dựng dashboard trong Langfuse hay một công cụ local. File này quy định đúng nguồn dữ liệu, phép tổng hợp, đơn vị và threshold cho sáu panel.

Trường `query` trong YAML là pseudocode mô tả phép tính, không phải câu lệnh để copy nguyên vào mọi công cụ. Bạn chuyển cùng logic đó sang cú pháp của công cụ đã chọn.

Lab không bắt buộc một công cụ dashboard cụ thể. Repo này có dashboard runtime tại `http://127.0.0.1:8000/dashboard`, dùng API `GET /dashboard/data` đọc `data/logs.jsonl`. Điều quan trọng khi chấm là dashboard có dữ liệu thật, đủ sáu panel, đọc được time range/đơn vị/threshold và khớp logic trong `config/dashboard.yaml`.

## Mapping dữ liệu

| Panel | Event/field | Phép tổng hợp |
|---|---|---|
| Latency | `response_sent.latency_ms/ttft_ms` | latency P50/P95/P99 và TTFT P95 |
| Traffic | `request_received` | count, request/phút |
| Errors | `request_received`, `request_failed`, `error_type`, `tool_success` | error rate, breakdown và retrieval success |
| Cost | `response_sent.cost_usd` | tổng theo phút và toàn cửa sổ |
| Tokens | `response_sent.tokens_in/tokens_out` | tổng theo từng field |
| Quality | `response_sent.quality_score` | mean |

Giữ time range mặc định 60 phút, refresh 30 giây và hiển thị threshold/SLO line. Giá trị chính xác nằm trong `config/dashboard.yaml`; không tự đổi contract chỉ để ảnh dashboard đẹp hơn.

## Cách dựng

1. Hoàn thiện logging/PII và chạy API.
2. Chạy `python scripts/run_cp2_workload.py --label production --limit 10` để tạo workload không chứa PII; script dùng `.env` và gọi FastAPI trong cùng tiến trình.
3. Mở `http://127.0.0.1:8000/dashboard` sau khi khởi động API theo `docs/SETUP.md`. Trang gọi `/dashboard/data` mỗi 30 giây và chỉ hiển thị log trong 60 phút gần nhất.
4. Đối chiếu từng phép tính, đơn vị và threshold với `config/dashboard.yaml`. Langfuse vẫn là nơi mở trace/prompt version để điều tra sâu.
5. Chạy validator:

```bash
python scripts/validate_dashboard.py
```

Validator kiểm tra cấu trúc contract; nó không thể chứng minh biểu đồ trong ảnh dùng đúng dữ liệu. Evidence runtime vẫn bắt buộc. Nếu dashboard báo chưa có dữ liệu, chạy workload rồi làm mới trang; log cũ hơn 60 phút không xuất hiện trong cửa sổ mặc định.

## Cách kiểm tra runtime

1. Lưu ảnh baseline và giá trị P95/error/cost hiện tại.
2. Bật một incident practice, ví dụ `python scripts/inject_incident.py --scenario <practice_scenario>`.
3. Chạy lại load test với cùng input và concurrency.
4. Xác nhận panel liên quan thay đổi theo đúng hướng theo loại practice scenario đã chọn.
5. Lọc log chậm, lấy correlation ID rồi mở trace có cùng ID.
6. Tắt incident bằng `python scripts/inject_incident.py --scenario <practice_scenario> --disable`.

Ảnh dashboard phải nhìn được tên panel, time range, đơn vị và threshold. Báo cáo phải dẫn lại trace ID hoặc log line dùng để giải thích thay đổi.
