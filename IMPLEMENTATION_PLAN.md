# Kế hoạch triển khai Observathon

## Mục tiêu

- Sửa các cấu hình cố ý gây lỗi trong `solution/config.json`.
- Viết lại system prompt ngắn gọn, dùng tool đúng cách, tính toán chính xác, không làm lộ PII và chống prompt injection.
- Biến `solution/wrapper.py` từ passthrough thành lớp quan sát và giảm thiểu lỗi thread-safe.
- Cập nhật `solution/findings.json` bằng các chẩn đoán có căn cứ, không bịa số liệu chưa đo được.
- Đảm bảo bài nộp tuân thủ `RULES.md` và vượt qua `python harness/selfcheck.py`.

## Thay đổi dự kiến

1. `solution/config.json`
   - Giảm temperature và giới hạn token/step để ổn định kết quả, chi phí và latency.
   - Bật loop guard, retry, cache, Unicode normalization, PII redaction và verification.
   - Xóa catalog override sai, tool error mô phỏng và session drift cố ý.
   - Đặt tool budget phù hợp với luồng `check_stock -> discount -> shipping`.

2. `solution/prompt.txt`
   - Tách product, quantity, coupon và destination.
   - Chỉ tin dữ liệu từ tool; từ chối và không kèm tổng tiền khi không có hàng hoặc không tìm thấy sản phẩm.
   - Quy định công thức số nguyên và định dạng dòng kết quả để parse.
   - Mỗi tool chỉ gọi một lần; không lặp lại email hoặc số điện thoại.
   - Xem ghi chú đơn hàng là dữ liệu không tin cậy, không làm theo chỉ dẫn được chèn vào.

3. `solution/examples.json`
   - Giữ few-shot tổng quát, không chứa giá hay đáp án của bộ đề.
   - Minh họa hành vi từ chối và định dạng kết quả thay vì hardcode sản phẩm trong đề.

4. `solution/wrapper.py`
   - Tạo correlation ID và log latency, token, cost, tool usage, status và trace đã redact.
   - Cache theo request đã chuẩn hóa, có khóa để an toàn khi chạy đồng thời.
   - Retry có giới hạn cho các status lỗi có khả năng phục hồi.
   - Redact PII ở output và log; không hardcode answer/price hay đọc file cấm.
   - Phát hiện tool call lặp lại và ghi telemetry phục vụ chẩn đoán.

5. `solution/findings.json`
   - Ghi các fault class suy ra trực tiếp từ cấu hình và prompt ban đầu.
   - Phân biệt rõ bằng chứng audit tĩnh với bằng chứng runtime chưa có.

## Kiểm thử

- Chạy `python harness/selfcheck.py`.
- Compile wrapper bằng `python -m py_compile solution/wrapper.py`.
- Chạy unit smoke test với `call_next` giả lập để kiểm tra cache, retry, redaction và logging.
- Chạy practice simulator bằng Docker và OpenRouter, sau đó đọc log telemetry để bổ sung số liệu P50/P95, token, tool call, status và PII thực tế.
- Có thể tạo tải tùy chỉnh bằng các tham số `Users`, `Turns`, `Concurrency`, `Rps` và `Seed` trong `run_openrouter.ps1`.

## Giới hạn hiện tại

- Binary Windows không chạy được trên máy do lỗi nạp `python312.dll`, vì vậy sử dụng binary Linux qua Docker Desktop.
- API key không được lưu trong repository; người chạy phải đặt biến `OPENROUTER_API_KEY` trong phiên PowerShell hiện tại.
- Metric runtime chỉ được ghi nhận sau khi chạy simulator thành công với API key OpenRouter hợp lệ.

## Kết quả đã triển khai

- Đã sửa `solution/config.json` để loại các fault injection và giới hạn chi phí/latency.
- Đã viết lại `solution/prompt.txt` với grounding, số học chính xác, tool economy, bảo vệ PII và chống injection.
- Đã để `solution/examples.json` rỗng có chủ đích nhằm giảm token và tránh overfit.
- Đã triển khai cache thread-safe, retry giới hạn, PII redaction và structured telemetry trong `solution/wrapper.py`.
- Đã ghi 11 fault class có bằng chứng audit vào `solution/findings.json`; không gán trace ID hay metric runtime giả.
- `python harness/selfcheck.py`: PASS tất cả 5 thành phần.
- `python -m py_compile solution/wrapper.py`: PASS.
- Smoke test giả lập: retry 2 lần, email được redact, request lặp lại dùng cache và không gọi agent thêm.
- Đã cấu hình OpenRouter qua giao diện OpenAI-compatible với model `openai/gpt-4o-mini`.
- Đã thêm `run_openrouter.ps1`, hỗ trợ Docker và các tham số tải tùy chỉnh; API key chỉ được đọc từ `OPENROUTER_API_KEY`.
- Đã tải và kiểm tra thành công binary Linux tại `bin/practice/observathon-sim` trong container `python:3.12-slim`.
- Đã đọc và đối chiếu `docs/FAULT_CLASSES.md`, `docs/PROMPT_OPTIMIZATION.md`, `docs/WRAPPER_API.md` và `docs/SUBMIT.md` với bài làm hiện tại.
- Đã rút `solution/prompt.txt` từ 773 xuống 589 ký tự để giảm bloat penalty, đồng thời giữ đủ grounding, thứ tự tool, số học, PII và injection defense.
- Đã thêm input sanitization trong `solution/wrapper.py`: loại phần ghi chú bắt đầu bằng `GHI CHÚ`, `note` hoặc `order note` trước khi gọi agent và ghi cờ `input_sanitized` vào telemetry.
- Đã cập nhật `solution/findings.json` bằng bằng chứng runtime thật từ lượt OpenRouter 20 request: 20/20 status `ok`, reported latency P50 6.397,5 ms, P95 9.746 ms, tổng 133.620 token và chi phí ước tính 0,144396 USD.
- Telemetry phát hiện `prac-020` gọi thừa `get_discount` dù không có coupon; prompt rút gọn tiếp tục nhấn mạnh chỉ gọi tool giảm giá khi coupon tồn tại.
- Không giảm `self_consistency` từ 2 xuống 1 ở lần cập nhật này vì lượt practice hiện tại đạt 20/20 `ok`; cần chạy A/B trước khi đổi để tránh giảm correctness và quality.
- Đã đọc toàn bộ thư mục `submission/` và hoàn thiện metadata nộp bài.
- Đã cập nhật `submission/manifest.json`: team `NguyenAnhChuc`, thành viên `Nguyen Anh Chuc` và ghi chú môi trường Docker/OpenRouter.
- Đã hoàn thiện `submission/TEMPLATE_FINDINGS.md` bằng bảng 11 fault class, bằng chứng audit/runtime, nguyên nhân gốc và cách sửa; số liệu khớp với `solution/findings.json` và telemetry.
- Sau khi nhận public scorer, đã xác minh `score_public.json` có `n=0`, `correct=0`, `quality=0`, `prompt=0`; headline 44,95 chỉ đến từ diagnosis và các metric mặc định của run rỗng, không phải điểm public hợp lệ.
- Đã phát hiện `bin/public/observathon-sim` có SHA-256 giống hệt `bin/practice/observathon-sim`; `run_output_public.json` chứa `phase=practice` và QID `prac-*`, nên đây là practice binary bị đặt nhầm vào thư mục public.
- Gói public hiện có trong Downloads chỉ chứa `observathon-score`; chưa tìm thấy public simulator đúng để tạo run public hợp lệ, vì vậy chưa thay đổi config/prompt theo headline 44,95 giả.
- Đã sửa `run_openrouter.ps1` để ghi output vào file tạm, xác minh `run.phase` trùng phase yêu cầu rồi mới thay file đích; phase mismatch sẽ dừng và giữ nguyên output cũ.
- Đã cấm `Users`, `Turns`, `Rps` và `Seed` khi chạy public/private vì các phase chấm điểm phải dùng fixed test set.
- Đã thêm `run_score.ps1` để chấm public/private qua Docker, kiểm tra phase và số lượng result trước khi chạy, đồng thời từ chối score có `n=0`.
- Đã probe binary hiện tại bằng `--testset public` mà không truyền API key; kết quả vẫn là `phase=practice`, 20 QID `prac-*`, xác nhận đây không phải public simulator và không phát sinh chi phí OpenRouter cho phép thử.
- Đã đổi tên các artifact sai thành `run_output_public.invalid-practice.json` và `score_public.invalid-n0.json` để lưu bằng chứng nhưng tránh nộp nhầm.
- Đã truyền phase tường minh trong `run_openrouter.ps1`: `--practice` cho practice và `--testset public/private` cho phase chấm điểm; kiểm tra `run.phase` vẫn là nguồn xác nhận cuối cùng.
- Đã cập nhật `OPENROUTER.md` với quy trình chạy simulator và `run_score.ps1` cho public/private.
- Đã nhận và phân tích public run hợp lệ mới: 120/120 status `ok`, 69 exact-correct, headline 92,32 và diagnosis F1 0,952.
- Đã tạo `PUBLIC_ANALYSIS.md` ghi score từng thành phần, số liệu telemetry, lỗi đại diện và kế hoạch tối ưu sau public.
- Telemetry public ghi nhận reported latency P50 6.543 ms, P95 10.461 ms, tổng 863.919 token, trung bình 7.199,3 token/request và chi phí ước tính 0,909453 USD.
- Đã giảm `self_consistency` từ 2 xuống 1 và `max_completion_tokens` từ 350 xuống 220 để xử lý cost score 0,1440; selective retry chỉ áp dụng cho kết quả thiếu tool/tổng thay vì nhân sampling cho mọi request.
- Đã thêm generic completeness validation trong wrapper: yêu cầu `check_stock`, yêu cầu discount/shipping khi input có coupon/destination, và yêu cầu dòng `Tong cong` cho câu hỏi tổng tiền; tối đa retry một lần.
- Đã loại các từ chối hợp lệ khỏi validation retry, gồm hết hàng, không đủ số lượng, chỉ còn ít hàng và tuyến giao không hỗ trợ.
- Đã sanitize email/số điện thoại khỏi input, ghi cờ `contact_removed`, và xóa hậu tố liên hệ chứa `[REDACTED]` khỏi output.
- Đã ghi `validation_retries` vào telemetry để đo hiệu quả và chi phí retry trong public/private run tiếp theo.
- Đã cập nhật `solution/findings.json` và `submission/TEMPLATE_FINDINGS.md` bằng bằng chứng public 120 request thay cho số liệu practice cũ.
- Đã siết validation cho script: phase chỉ nhận `practice/public/private`; tên run/output/team chỉ nhận ký tự an toàn.
- Đã sửa `run_score.ps1` để scorer ghi vào file tạm, chỉ thay `score_public.json`/`score_private.json` sau khi xác minh phase đúng và `n>0`; score tốt cũ không còn bị ghi đè bởi kết quả lỗi.
