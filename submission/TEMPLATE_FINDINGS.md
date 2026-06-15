# Findings - Team NguyenAnhChuc

Tệp được chấm điểm là `solution/findings.json`. Bảng này tóm tắt chẩn đoán để người đọc đối chiếu với cấu hình, prompt và telemetry trong `logs/`.

| fault_class | Bằng chứng | Nguyên nhân gốc | Cách sửa |
|---|---|---|---|
| `arithmetic_error` | Audit ban đầu: `temperature=1.6`, chưa bật verify và prompt không quy định công thức số nguyên. | Sampling biến động và yêu cầu tính toán không rõ ràng. | Đặt temperature 0.2, bật verify và nêu công thức floor chính xác trong prompt. |
| `tool_overuse` | Trace `prac-020` gọi `get_discount` dù câu hỏi không có coupon. Cấu hình ban đầu có `tool_budget=0`. | Không có giới hạn tool và quy tắc gọi tool đủ chặt. | Đặt `tool_budget=3`, mỗi tool tối đa một lần và chỉ gọi discount khi có coupon. |
| `infinite_loop` | Audit ban đầu: `loop_guard=false`, `max_steps=12`; wrapper chưa phát hiện action lặp. | Tool action có thể lặp cho đến khi hết step. | Bật loop guard, giảm max steps và ghi repeated actions vào telemetry. |
| `latency_spike` | Public 120 request: reported latency P50 6.543 ms, P95 10.461 ms, max 147.269 ms. | Agent path dài, nhiều token và cấu hình ban đầu không có timeout/cache. | Timeout hữu hạn, cache, giảm context/token/step và theo dõi P50/P95. |
| `pii_leak` | Public đã che raw PII nhưng nhiều output còn hậu tố `(lien he: [REDACTED])`, ví dụ `pub-010`, `pub-014`, `pub-100`. | Prompt và cấu hình ban đầu không bảo vệ PII; redaction đơn thuần còn để lại ngữ cảnh liên hệ. | Xóa contact khỏi input, cấm echo email/phone, redact log/output và dọn hậu tố liên hệ. |
| `tool_failure` | Audit ban đầu: tắt Unicode normalization và có `catalog_override` sai. | Tên thành phố có dấu có thể không match, dữ liệu override trái source of truth. | Bật normalization và xóa catalog override. |
| `error_spike` | Audit ban đầu: `tool_error_rate=0.18`, retry tắt. | Lỗi tool ngắt quãng không có đường phục hồi. | Xóa fault injection và retry tối đa hai lần với backoff ngắn. |
| `quality_drift` | Audit ban đầu: `session_drift_rate=0.06`, không reset context. | Context dài tích lũy suy giảm chất lượng có chủ đích. | Đặt drift về 0, reset context định kỳ và dùng sampling ổn định. |
| `fabrication` | Prompt ban đầu luôn yêu cầu tổng tiền, không có chính sách từ chối khi hết hàng/không tìm thấy. | Model bị thúc đẩy trả lời dù thiếu dữ liệu đáng tin cậy. | Chỉ dùng dữ liệu tool; từ chối không kèm tổng nếu item/route không khả dụng. |
| `prompt_injection` | Audit trust boundary: prompt ban đầu không phân biệt ghi chú với instruction. Wrapper mới ghi `input_sanitized` khi loại `GHI CHÚ`/`note`. | Nội dung khách hàng nằm cùng kênh với chỉ dẫn điều khiển agent. | Prompt coi note là dữ liệu không tin cậy và wrapper loại note injection trước agent call. |
| `cost_blowup` | Public dùng 863.919 token, trung bình 7.199,3 token/request, chi phí telemetry ước tính 0,909453 USD; cost score 0,1440. | Context/completion ban đầu quá lớn; `self_consistency=2` nhân sampling cho mọi request. | Dùng economy tier, cache, prompt 589 ký tự, completion cap 220 và selective retry với `self_consistency=1`. |

## Kết quả public đã đo

- Headline 92,32; diagnosis F1 0,952.
- 120/120 request có status `ok`; 69 exact-correct.
- Reported latency: P50 6.543 ms; P95 10.461 ms.
- Tổng token: 863.919; trung bình 7.199,3 token/request.
- Chi phí telemetry ước tính: 0,909453 USD; cost sub-score 0,1440.
- Phát hiện bỏ discount ở `pub-062`, `pub-080`, dừng sớm ở `pub-086` và không gọi stock tool ở `pub-100`.
