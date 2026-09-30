# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`; duration: `5m`; owner: `student-on-call`.
- Kênh thông báo dự kiến: Slack `#k4-l3b-alerts` (lab chỉ mô tả rule, chưa cấu hình gửi Slack thật).
- SLI/SLO liên quan: `response_sent.latency_ms <= 3000`.
- Điều kiện: P95 latency > 3000 ms liên tục 5 phút; chỉ đánh giá khi có request trong cửa sổ.
- Ảnh hưởng tới người dùng: chờ câu trả lời quá lâu.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel latency và TTFT, ghi lại khoảng thời gian P95 vượt ngưỡng.
  2. Lọc `response_sent` có `latency_ms` cao trong `data/logs.jsonl`, lấy `correlation_id`.
  3. Mở trace cùng ID, so thời gian retrieval và generation; kiểm tra prompt version.
- Mitigation tạm thời: nếu regression xuất hiện sau promote prompt, rollback label `production`; nếu retrieval chậm, khôi phục nguồn retrieval hoặc giảm tải sau khi xác nhận bằng trace.

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`; duration: `5m`; owner: `student-on-call`.
- Kênh thông báo dự kiến: Slack `#k4-l3b-alerts`.
- SLI/SLO liên quan: tỷ lệ request có `response_sent` thành công.
- Điều kiện: `request_failed / request_received > 2%` liên tục 5 phút; không chia cho 0 khi chưa có traffic.
- Ảnh hưởng tới người dùng: request không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel errors, xác nhận error rate và nhóm `error_type` tăng.
  2. Lọc `request_failed` cùng khoảng thời gian, lấy một `correlation_id` tiêu biểu.
  3. Mở trace tương ứng để xác định observation lỗi và xem prompt/version liên quan.
- Mitigation tạm thời: xử lý dependency gây lỗi, rollback thay đổi liên quan nếu có evidence; kiểm tra lại tỷ lệ thành công bằng cùng workload.

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`; duration: `10m`; owner: `student-on-call`.
- Kênh thông báo dự kiến: Slack `#k4-l3b-alerts`.
- SLI liên quan: tỷ lệ event `tool_name=retrieval` có `tool_success=true`; nguồn gồm `response_sent` và `request_failed`.
- Điều kiện: retrieval success < 90% liên tục 10 phút; chỉ đánh giá khi có ít nhất một lần retrieval.
- Ảnh hưởng tới người dùng: không lấy được context hoặc request trả lỗi.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel errors/retrieval success và khoảng thời gian tỷ lệ giảm.
  2. Lọc `tool_name=retrieval`, `tool_success=false` trong log, lấy `correlation_id`.
  3. Mở trace tương ứng, kiểm tra observation retrieval và `error_type`.
- Mitigation tạm thời: khôi phục nguồn retrieval hoặc tắt practice scenario gây lỗi, sau đó chạy lại cùng workload để xác nhận tỷ lệ phục hồi.
