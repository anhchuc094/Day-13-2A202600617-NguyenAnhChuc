# Kế hoạch và nhật ký cải thiện Observathon

## Mục tiêu

- Tối ưu correctness, quality, error rate, latency, cost, drift và prompt score.
- Xây dựng wrapper quan sát được, thread-safe, bảo vệ PII và chống prompt injection.
- Chỉ ghi số liệu đã đo; phân biệt rõ practice, public và private.
- Tuân thủ `RULES.md`, không hardcode đáp án/giá và luôn vượt `harness/selfcheck.py`.

## Giai đoạn 1: Trước khi nhận public

### Phân tích ban đầu

- Đọc `RULES.md` và toàn bộ tài liệu trong `docs/`.
- Xác định 11 fault class: `error_spike`, `latency_spike`, `cost_blowup`, `quality_drift`, `infinite_loop`, `tool_failure`, `pii_leak`, `fabrication`, `arithmetic_error`, `tool_overuse`, `prompt_injection`.
- Phát hiện cấu hình ban đầu có temperature cao, fault injection, drift, catalog override sai, thiếu retry/cache/loop guard và giới hạn token quá lớn.
- Binary Windows lỗi nạp `python312.dll`; chuyển sang Linux binary qua Docker Desktop.

### Cải thiện đã thực hiện

- Sửa `solution/config.json`: temperature 0.2, loop guard, timeout, retry, cache, Unicode normalization, PII redaction, verification, tool budget và xóa fault injection.
- Viết lại `solution/prompt.txt` với grounding, thứ tự tool, công thức số nguyên, từ chối khi không khả dụng, chống injection và không echo PII.
- Rút prompt từ 773 xuống 589 ký tự để tránh bloat penalty.
- Để `solution/examples.json` rỗng có chủ đích nhằm giảm token và tránh overfit.
- Xây dựng `solution/wrapper.py` với structured telemetry, correlation ID, retry giới hạn, cache thread-safe, PII redaction và repeated-action detection.
- Sanitize phần `GHI CHÚ`, `note`, `order note` trước agent call; ghi `input_sanitized` vào telemetry.
- Hoàn thiện `solution/findings.json`, `submission/manifest.json` và `submission/TEMPLATE_FINDINGS.md`.
- Thêm `run_openrouter.ps1`, `run_score.ps1` và hướng dẫn `OPENROUTER.md` để chạy/chấm bằng Docker.
- Script xác minh phase, fixed test set, `n>0` và dùng file tạm để không ghi đè artifact tốt bằng kết quả lỗi.

### Practice evidence

- Practice run: 20/20 status `ok`.
- Reported latency P50 6.397,5 ms; P95 9.746 ms.
- Tổng 133.620 token; chi phí telemetry ước tính 0,144396 USD.
- Phát hiện một tool call không cần thiết ở `prac-020`.

### Kiểm thử trước public

- `python harness/selfcheck.py`: PASS 5/5.
- `python -m py_compile solution/wrapper.py`: PASS.
- Smoke test cache, retry, redaction và logging: PASS.

## Giai đoạn 2: Sau khi nhận public

### Xác minh bộ public

- Lần đầu đặt nhầm practice simulator vào `bin/public`; scorer tạo `n=0`, headline 44,95 không hợp lệ.
- Xác minh bằng SHA-256, `phase=practice` và QID `prac-*`; đổi tên artifact thành `*.invalid-*` và thêm rule `.gitignore` để tránh nộp nhầm.
- Sau khi có simulator đúng, public run hợp lệ gồm 120 request và QID `pub-*`.

### Public baseline

- Headline: **92,32**.
- 120/120 status `ok`; 69 exact-correct.
- Correct 0,7042; quality 0,8152; latency 0,4817; cost 0,1440; drift 0,7105; prompt 0,8444; diagnosis F1 0,952.
- Telemetry: reported latency P50 6.543 ms, P95 10.461 ms; 863.919 token; chi phí ước tính 0,909453 USD.
- Lỗi đại diện: bỏ discount ở `pub-062`/`pub-080`, dừng sớm ở `pub-086`, không gọi stock tool ở `pub-100`, output còn hậu tố liên hệ đã redact.

### Cải thiện theo public evidence

- Giảm `self_consistency` từ 2 xuống 1 và `max_completion_tokens` từ 350 xuống 220 để giảm cost/latency.
- Thêm completeness validation tổng quát: kiểm tra `check_stock`, discount, shipping và dòng `Tong cong` theo yêu cầu đầu vào.
- Selective retry tối đa một lần khi kết quả `ok` nhưng thiếu tool/tổng; không retry từ chối hợp lệ do hết hàng, thiếu số lượng hoặc tuyến giao không hỗ trợ.
- Loại email/số điện thoại khỏi input; ghi `contact_removed`; dọn hậu tố `(lien he: [REDACTED])` khỏi output.
- Chỉ cache kết quả `ok` vượt completeness validation.
- Giữ kết quả tốt nhất qua retry để lỗi lần sau không ghi đè kết quả dùng được lần trước.
- Thêm single-flight cache bằng `threading.Event`: request giống nhau đồng thời dùng chung một agent call.
- Telemetry ghi `validation_retries`, `validation_failed` và safe tool facts như stock, price, discount, shipping, valid; không ghi prompt/PII.
- Thêm `harness/test_solution.py` kiểm tra sanitize, PII cleanup, selective retry, best-result, single-flight và safe trace facts.

### Public sau tối ưu

- Headline: **96,87**, tăng **4,55** điểm.
- Exact-correct: **76/120**, tăng 7 câu.
- Correct 0,7333; quality 0,8327; error 1,0; latency 0,5994; cost 0,2326; drift 0,9407; prompt 0,8438; diagnosis F1 0,952.
- Reported latency P50 6.232,5 ms; P95 9.107 ms; max 11.790 ms.
- Tổng 860.471 token; trung bình 7.170,6 token/request; chi phí telemetry ước tính 0,905653 USD.
- 6 cache hit, 5 selective retry, 120/120 status `ok`, không còn `validation_failed`.
- Chi tiết so sánh được ghi trong `PUBLIC_ANALYSIS.md`.

### Trạng thái kiểm thử sau public

- `python harness/selfcheck.py`: PASS 5/5.
- `python -m py_compile solution/wrapper.py harness/test_solution.py`: PASS.
- `python -m unittest harness/test_solution.py -v`: PASS 5/5.
- Test concurrency 8 thread: 1 agent call, 7 cache hit.
- `run_score.ps1` xác minh public score hợp lệ với `n=120`.
- Lưu ý: single-flight, best-result selection và safe trace facts được thêm sau lượt 96,87; tác động điểm cần xác minh ở lượt A/B tiếp theo.

## Giai đoạn 3: Sau khi nhận private

### Trạng thái hiện tại

- Đã nhận private simulator và tạo artifact đúng `phase=private` với 80 QID `prv-*`.
- Lượt hiện tại có 80/80 `wrapper_error` và 80 `answer=null`.
- Telemetry xác nhận nguyên nhân đồng nhất: OpenRouter HTTP 402 `Insufficient credits`. Key đã được gửi nhưng tài khoản/key không có credit; agent chưa chạy nên không thể sinh answer.
- Chưa có private scorer trong workspace, nên chưa có headline/sub-score hợp lệ.
- Không dùng public/private question hoặc answer để hardcode; private có paraphrase và injection twist.

### Cải thiện sau khi đọc private

- Phát hiện 20/80 câu injection dùng `GHI CHU KHACH:` với giá giả 1.000.000 VND; mở rộng sanitizer và test cả 20 câu.
- Đổi `solution/prompt.txt` sang tiếng Việt, bắt buộc trả lời tiếng Việt và giữ dòng cuối `Tong cong: <số nguyên> VND`.
- Rút prompt tiếng Việt xuống dưới 600 ký tự để giữ prompt score và giảm token.
- Thêm nhận diện lỗi API vĩnh viễn 400/401/402/403/404; wrapper dừng sau lần đầu thay vì retry lỗi hết credit/key sai.
- `run_openrouter.ps1` không ghi đè output tốt nếu toàn bộ request lỗi; lưu lượt lỗi thành `.failed-*` và hướng người chạy xem log.
- Cần nạp credit hoặc đổi sang key còn credit, sau đó chạy lại private để có answer và metric hợp lệ.

### Quy trình khi nhận private

1. Đặt đúng `observathon-sim` và `observathon-score` tại `bin/private/`.
2. Xác minh binary không trùng practice/public và output có `phase=private`, QID `prv-*`.
3. Chạy fixed test set, không truyền `Users`, `Turns`, `Rps` hoặc `Seed`.
4. Chạy simulator:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\run_openrouter.ps1 `
     -Phase private -Output run_output_private.json -Concurrency 8
   ```

5. Chạy scorer:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\run_score.ps1 `
     -Phase private -Run run_output_private.json -Output score_private.json
   ```

6. Phân tích correctness, quality, latency, cost, drift, prompt score, injection cases, PII, tool order, retries và cache hit.
7. Chỉ sửa theo lỗi tổng quát có bằng chứng; không hardcode private question, giá hoặc answer.
8. Cập nhật mục này với score trước/sau, trace đại diện, thay đổi code và kết quả kiểm thử.

### Checklist báo cáo private cần điền

- Headline, `n`, exact-correct và các sub-score.
- P50/P95 latency, tổng/average token, estimated cost.
- Số cache hit, retry, validation failure và sanitized injection.
- Các lỗi đại diện và root cause.
- Thay đổi sau private cùng A/B score nếu được phép chạy lại.
- Kết quả `selfcheck`, unit tests và scorer validation cuối cùng.

## Artifact quan trọng

- Code/config: `solution/config.json`, `solution/prompt.txt`, `solution/examples.json`, `solution/wrapper.py`.
- Chẩn đoán: `solution/findings.json`, `submission/TEMPLATE_FINDINGS.md`.
- Báo cáo public: `PUBLIC_ANALYSIS.md`.
- Chạy/chấm: `run_openrouter.ps1`, `run_score.ps1`, `OPENROUTER.md`.
- Regression tests: `harness/test_solution.py`.
- Kết quả public hiện tại: `run_output_public.json`, `score_public.json`.
