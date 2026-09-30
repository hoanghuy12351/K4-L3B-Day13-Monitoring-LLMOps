# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Võ Huy Hoàng
- **MSSV:** 2A202602548
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/hoanghuy12351/K4-L3B-Day13-Monitoring-LLMOps
- **Commit SHA cuối:** Chưa tạo commit nộp; điền SHA được nộp trên LMS sau khi rà soát và commit toàn bộ artifact CP4.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602548`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence                      | Đường dẫn                                                                                                      |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Pytest cuối CP4               | [01-pytest.txt](evidence/01-pytest.txt)                                                                        |
| Log validator cuối CP4        | [02-log-validator.txt](evidence/02-log-validator.txt)                                                          |
| Dashboard validator           | [03-dashboard-validator.txt](evidence/03-dashboard-validator.txt)                                              |
| Structured log                | [04-structured-log.png](evidence/04-structured-log.png)                                                        |
| PII redaction                 | [05-pii-redaction.png](evidence/05-pii-redaction.png)                                                          |
| Trace list                    | [06-trace-list.png](evidence/06-trace-list.png)                                                                |
| Trace waterfall               | [07-trace-waterfall.png](evidence/07-trace-waterfall.png)                                                      |
| Trace metadata                | [08-trace-metadata.png](evidence/08-trace-metadata.png)                                                        |
| Prompt versions               | [09-prompt-versions.png](evidence/09-prompt-versions.png)                                                      |
| Prompt rollback               | [10-prompt-rollback.png](evidence/10-prompt-rollback.png)                                                      |
| Dashboard runtime (phần trên) | [11-dashboard-overview.png](evidence/11-dashboard-overview.png)                                                |
| Dashboard runtime (phần dưới) | [11-dashboard-bottom.png](evidence/11-dashboard-bottom.png)                                                    |
| CP3 workload và recovery      | [15-cp3-workload.txt](evidence/15-cp3-workload.txt)                                                            |
| Incident metric               | [12-incident-metric.png](evidence/12-incident-metric.png), [số liệu chi tiết](evidence/12-incident-metric.txt) |
| Incident log                  | [13-incident-log.png](evidence/13-incident-log.png), [số liệu chi tiết](evidence/13-incident-log.txt)          |
| Incident trace                | [14-incident-trace.png](evidence/14-incident-trace.png), [số liệu chi tiết](evidence/14-incident-trace.txt)    |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline             | Kết quả cuối                                     | Nhận xét                                                                |
| ----------------------- | -------------------- | ------------------------------------------------ | ----------------------------------------------------------------------- |
| `validate_logs.py`      | 30/100               | 100/100 (110 records)                            | 0 missing fields/context sau CP3 và recovery check                      |
| `validate_dashboard.py` | 6/6 contract         | 6/6 contract + runtime                           | Validator không tự chứng minh dữ liệu runtime                           |
| `pytest`                | 22 passed            | 26 passed, 1 warning                             | Chạy lại ở CP4; warning deprecation của Starlette/anyio                 |
| Số traces hợp lệ        | Chưa có CP2 workload | 10 root traces trong session `cp2-safe-workload` | Mỗi root có retrieval và generation                                     |
| Số PII leak             | 0 trong baseline     | 0/110 records                                    | Theo `validate_logs.py`; không khẳng định mọi dữ liệu ngoài log         |
| Latency P95 / TTFT P95  | Chưa đo CP2          | 2609.20 / 51.00 ms                               | Ảnh dashboard lúc 21:46:47 ngày 30/09/2026, cửa sổ 60 phút, 13 requests |
| Retrieval success rate  | Chưa đo CP2          | 100.00%                                          | Cùng ảnh/cửa sổ; cỡ mẫu nhỏ, không suy ra SLO 28 ngày                   |
| CP3 latency P95         | Chưa chạy challenge  | 3603.60 ms tại phút 15:36 UTC, 5 requests        | Vượt ngưỡng challenge 2000 ms và dashboard 3000 ms; error rate vẫn 0%   |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` xóa context cũ ở đầu mỗi request, chỉ chấp nhận header `x-request-id` khớp `req-<8-hex>`, nếu không thì sinh UUID rút gọn theo cùng format. ID được bind vào `structlog.contextvars`, lưu ở `request.state`, truyền vào `LabAgent.run`, ghi vào trace metadata và trả lại trong response header `x-request-id`.
- **Các metadata được ghi vào structured log:** `user_id` không được ghi thô mà được SHA-256 rồi rút gọn thành `user_id_hash`; context còn có `session_id`, `feature`, `model`, `env`, `correlation_id`. Event `response_sent` bổ sung latency, TTFT, token vào/ra, cost, quality proxy và trạng thái retrieval; event lỗi chỉ ghi loại lỗi cùng preview đã scrub.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` đứng trước `JsonlFileProcessor` và `JSONRenderer` trong processor chain. `summarize_text` cũng scrub trước khi tạo preview. Bốn rule che email, số điện thoại Việt Nam, CCCD 12 số và thẻ thanh toán; input/output thô không được capture vào Langfuse.
- **Cách kiểm chứng kết quả:** `evidence/05-pii-redaction.png` gửi một input chứa bốn PII giả rồi đối chiếu log runtime, kết quả `PASS` và chỉ còn các token `[REDACTED_*]`. Lần chạy CP4 của `validate_logs.py` kiểm tra 110 records: 0 thiếu field, 0 thiếu context, 0 potential PII leak, tổng 100/100.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chạy `scripts/run_cp2_workload.py --label production --limit 10` bằng key của project trong `.env`, với 10 câu hỏi tổng hợp không chứa PII. Lọc Langfuse `isRootObservation:true` và `sessionId:*cp2-safe-workload*` cho đúng 10 root observations; xem `evidence/06-trace-list.png`. Tên project hiện tại chưa khớp mẫu rubric như đã ghi ở mục 1.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` chứa hai child `retrieval` (retriever, ghi `doc_count`) và `generation` (model, managed prompt, token usage, cost). Waterfall thật: trace `0ca1c2b899189632c1e5c6f962a6c31d` trong `evidence/07-trace-waterfall.png`.
- **Cách nối trace với log:** `correlation_id` là cùng giá trị trong structured log và metadata của root/child observation. Evidence an toàn `evidence/08-trace-metadata.png` dùng trace `4da328c0a59fac26ef91dc0416fbd2cb` và hiển thị `req-d930f830`, khớp log incident; ảnh vẫn có model, prompt name/version/label, token và cost nhưng không hiển thị public/secret key.
- **Prompt name:** `day13-chat`, lấy version/label thực từ Langfuse, không gán version giả trong code.
- **Version/label baseline:** v1 = `baseline`; sau rollback v1 cũng là `production`.
- **Version/label candidate:** v2 = `candidate` (vẫn là `latest`, không còn là `production`).
- **Trace ID của mỗi version:** cùng input an toàn: v1/baseline `baff3bbeac7e71579b83b1a4738525bf` (`req-e238a0be`); v2/candidate `601393b28cb5df259026b157456de4df` (`req-686f9bcc`). Request kiểm chứng sau promote dùng v2/production: `d2bde20233140d027b3f1d33f1c45734` (`req-eb5bda75`).
- **Cách promote và rollback `production`:** Chuyển label sang v2 trên Langfuse, chạy lại cùng input với `--label production --same-input --limit 1`, kiểm tra trace root ghi `prompt_version=2`, `prompt_label=production`. Sau đó gắn lại `production` cho v1; kiểm tra SDK cuối cùng trả `production=1`, `candidate=2`, `baseline=1`. Ảnh hai version và trạng thái rollback: `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `/dashboard` đọc `data/logs.jsonl` qua `/dashboard/data`, cửa sổ 60 phút, refresh 30 giây: latency P50/P95/P99 và TTFT; traffic; error rate và retrieval success; cost; input/output tokens; quality proxy. Ảnh phần trên/dưới `evidence/11-dashboard-overview.png` và `evidence/11-dashboard-bottom.png` cho thấy giá trị, đơn vị, ngưỡng. Cost/token có ngưỡng dạng chữ cho tổng, không vẽ đường ngang lên biểu đồ theo phút vì khác phép tổng hợp.
- **SLO và lý do chọn:** `config/slo.yaml` đặt 99.5% request có `response_sent` trong <=3000 ms trong 28 ngày. Đây là mục tiêu lab; P95 2609.20 ms trong snapshot 13 request không đủ chứng minh SLO 28 ngày.
- **Cách tính error budget:** 100% - 99.5% = 0.5%; nếu 10,000 requests trong cửa sổ 28 ngày thì tối đa 50 request có lỗi hoặc quá 3000 ms. Với 13 request thử nghiệm, không nên diễn giải tỷ lệ như độ tin cậy production.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>3000 ms, 5m), `HighErrorRate` (>2%, 5m), `LowRetrievalSuccess` (<90%, 10m) trong `config/alert_rules.yaml`; mỗi rule có severity, owner, Slack channel dự kiến và runbook tại `docs/alerts.md`. Đây là rule cấu hình của lab, **chưa tích hợp gửi Slack thật**.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`, cohort K4. `config/challenge.json` vẫn được ignore bởi `.gitignore`; không force-add hoặc đưa nội dung challenge riêng vào commit.
- **Khoảng thời gian điều tra:** `2026-09-30 22:36:20–22:36:37 +07` (`15:36:20–15:36:37 UTC`). Workload chính thức chạy 5 query với `--challenge --concurrency 5`.
- **Triệu chứng từ metrics:** tại phút `15:36 UTC`, dashboard ghi 5 request và latency P95 `3603.60 ms`, vượt ngưỡng challenge `2000 ms` và ngưỡng dashboard `3000 ms`. Năm giá trị server-side là `2653, 2654, 2654, 2654, 3841 ms`; error rate `0%` và retrieval success `100%`, nên đây là sự cố hiệu năng chứ không phải request thất bại. Client quan sát khoảng `15.7 s` cho mỗi request concurrent, cho thấy thêm thời gian xếp hàng ngoài timer của `LabAgent`.
- **Log line và correlation ID liên quan:** `data/logs.jsonl` dòng 99 có `event=response_sent`, `correlation_id=req-d930f830`, `latency_ms=3841`, `tool_name=retrieval`, `tool_success=true`, timestamp `2026-09-30T15:36:26.937084Z`. Log chọn đúng request chậm nhưng chưa đủ để kết luận span nào gây chậm.
- **Trace ID và span gây ảnh hưởng:** Langfuse trace `4da328c0a59fac26ef91dc0416fbd2cb` có cùng `correlation_id=req-d930f830`; root `lab-agent-run=3.85 s`, child `retrieval=2.50 s`, child `generation=0.16 s`. Retrieval là child span chiếm phần lớn thời gian; generation không phải bottleneck chính.
- **Root cause:** incident `rag_slow` làm `retrieve()` chờ đồng bộ `2.5 s`. Vì endpoint `/chat` là `async` nhưng gọi `agent.run()` và `time.sleep()` đồng bộ ngay trên event loop, các request concurrency 5 bị tuần tự hóa; do đó client latency tăng lên khoảng `15.7 s`. Khoảng chênh còn lại giữa root và hai child span có thể gồm prompt fetch/framework overhead, nhưng evidence hiện có không đủ để coi đó là root cause thứ hai.
- **Fix action:** hành động khôi phục đã thực hiện là `scripts/inject_incident.py --disable`; `/health` sau đó xác nhận `rag_slow=false`, `tool_fail=false`, `cost_spike=false`. Request kiểm tra `req-44a11d47` sau recovery trả HTTP 200 với `162 ms` server-side và `336.7 ms` client-observed, thấp hơn ngưỡng challenge `2000 ms`. Với production, cần thay retrieval blocking bằng I/O async hoặc chạy adapter sync trong thread pool, đặt timeout và trả fallback/circuit-breaker khi retriever chậm. Không sửa `mock_rag.py` chỉ để làm challenge biến mất vì đó là cơ chế inject sự cố có chủ đích.
- **Preventive measure:** thêm timeout/fallback cho retrieval, kiểm thử concurrency để phát hiện event-loop blocking, đo queue time/end-to-end latency bên cạnh timer trong `LabAgent`, và giữ alert `HighLatencyP95` cùng runbook bắt buộc đi theo metric → log → trace trước khi kết luận.
- **Giới hạn evidence:** cả metric, log và trace đều đã có ảnh đúng tên quy định cùng bản diễn giải `.txt`; ba evidence khớp cùng khoảng sự cố và `correlation_id=req-d930f830`. Các ảnh chỉ chứng minh lần chạy lab hiện tại, không đại diện cho độ tin cậy production dài hạn.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng một `correlation_id` do middleware quản lý và truyền cùng giá trị sang cả structured log lẫn Langfuse, thay vì dùng message hay user ID để join. Cách này định danh đúng một request, tránh ghi PII, đồng thời `clear_contextvars()` ngăn metadata rò sang request kế tiếp.
- **Một lỗi/blocker đã gặp:** Challenge trả HTTP 200 và retrieval success vẫn 100%, nên nếu chỉ nhìn error rate sẽ dễ kết luận sai là hệ thống bình thường. Đồng thời client latency khoảng 15.7 giây cao hơn nhiều so với `LabAgent.latency_ms` của từng request.
- **Cách tìm nguyên nhân và xử lý:** Bắt đầu từ spike P95 3603.60 ms để khoanh phút 15:36 UTC, chọn log chậm `req-d930f830`, rồi mở đúng trace có cùng ID. Waterfall cho thấy retrieval 2.50 giây, generation chỉ 0.16 giây. Đối chiếu code xác nhận `time.sleep()` trong retrieval sync chặn event loop của endpoint async và làm năm request concurrent xếp hàng. Sau khi tắt incident, request kiểm chứng giảm còn 162 ms server-side; fix production đề xuất là adapter async/thread pool kèm timeout, fallback và concurrency test.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics phát hiện triệu chứng và thời gian nhưng không cho biết request nào; log chọn request cụ thể bằng `correlation_id` và cung cấp latency/trạng thái; trace cùng ID phân rã thời gian theo span để bác bỏ generation và xác nhận retrieval là bottleneck. Root cause chỉ được kết luận sau khi ba lớp evidence khớp nhau.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt label cho phép đổi phiên bản mà không sửa code và rollback nhanh khi version mới làm chất lượng, latency hoặc cost xấu đi. Trace phải giữ version/label cùng token và cost để so sánh cùng workload. SLO 99.5%/28 ngày biến “nhanh” thành tiêu chí đo được và error budget 0.5% giới hạn số request lỗi/chậm trước khi ưu tiên độ tin cậy thay vì tiếp tục thay đổi.
- **Điều quan trọng nhất đã học:** Validator chỉ chứng minh contract; dashboard runtime, trace thật và chuỗi metric → log → trace mới chứng minh hệ thống quan sát được. HTTP 200 cũng không đồng nghĩa request đáp ứng SLO.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Tên project Langfuse hiện là `day13-k4-k3b-2A202602548`, chưa khớp mẫu `day13-k4-l3b-<MSSV>`; alert mới là cấu hình/runbook, chưa gửi Slack thật; workload nhỏ không chứng minh SLO 28 ngày; chưa tạo commit nộp và chưa có bằng chứng LMS.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit CP4 cuối dùng để lấy SHA nộp LMS.
- [x] Tất cả ảnh/output trong evidence index mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace bằng cùng khoảng sự cố và `correlation_id`.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và các ảnh được dùng trong index không lộ public/secret key; tên project vẫn có lỗi `k3b` đã nêu ở phần hạn chế.
- [x] Repository cài/chạy lại theo README; tests và hai validator đã chạy lại ở CP4.
- [x] Candidate files không có `.env`, credential hoặc PII thật theo kiểm tra CP4; PII giả chỉ xuất hiện trong test/evidence redaction có chủ đích, còn `config/challenge.json` và `.env` vẫn bị ignore.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
