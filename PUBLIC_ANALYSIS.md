# Báo cáo phân tích public

## Kết quả hiện tại

Public simulator đã chạy đúng phase với 120 request và public scorer trả về:

| Chỉ số | Điểm |
|---|---:|
| Headline | 92,32 |
| Correct | 0,7042 |
| Quality | 0,8152 |
| Error | 1,0000 |
| Latency | 0,4817 |
| Cost | 0,1440 |
| Drift | 0,7105 |
| Prompt | 0,8444 |
| Diagnosis F1 | 0,9520 |

Run có 120/120 status `ok`, 69 câu exact-correct. Telemetry của wrapper ghi nhận:

- Reported latency P50: 6.543 ms; P95: 10.461 ms; max: 147.269 ms.
- Wall time P50: 8.882 ms; P95: 13.669 ms; max: 151.560 ms.
- Tổng token: 863.919; trung bình 7.199,3 token/request.
- Chi phí telemetry ước tính: 0,909453 USD.
- 3 cache hit, không có retry và không có status lỗi.

## Vấn đề phát hiện

1. **Chi phí cao:** `self_consistency=2` nhân số lần sampling nhưng vẫn không ngăn được một số lỗi bỏ tool. Cost score chỉ đạt 0,1440.
2. **Bỏ coupon:** `pub-062` và `pub-080` không gọi `get_discount`, dẫn đến bỏ giảm giá WINNER.
3. **Dừng giữa quy trình:** `pub-086` chỉ gọi `check_stock`, sau đó hỏi người dùng về coupon thay vì tính tổng.
4. **Không gọi tool:** `pub-100` từ chối trả lời câu hỏi tồn kho/giá và không gọi `check_stock`.
5. **PII đã che nhưng output còn nhiễu:** nhiều câu giữ hậu tố `(lien he: [REDACTED])`, làm giảm độ gọn và chất lượng.
6. **Tool order chưa ổn định:** 7 request gọi `calc_shipping` trước `get_discount`.

## Thay đổi sau public

- Giảm `self_consistency` từ 2 xuống 1 để giảm sampling cost; dùng retry chọn lọc thay cho việc nhân mọi request.
- Giảm `max_completion_tokens` từ 350 xuống 220 vì prompt yêu cầu câu trả lời ngắn.
- Wrapper retry tối đa một lần khi kết quả `ok` nhưng thiếu tool bắt buộc hoặc thiếu dòng `Tong cong`.
- Không retry các từ chối hợp lệ như hết hàng, không đủ số lượng hoặc tuyến giao không hỗ trợ.
- Loại email/số điện thoại và cụm liên hệ khỏi input trước agent call; ghi `contact_removed` vào telemetry.
- Loại hậu tố liên hệ chứa `[REDACTED]` khỏi output.
- Ghi `validation_retries` để theo dõi lý do retry trong lần chạy tiếp theo.
- Dùng single-flight cache theo từng request key để các request giống nhau chạy đồng thời chỉ gọi agent một lần.
- Giữ kết quả tốt nhất qua các lần retry; lỗi ở lần hai không còn ghi đè một kết quả `ok` dùng được ở lần đầu.
- Không cache kết quả vẫn thiếu tool/tổng sau retry; ghi `validation_failed` để điều tra.
- Telemetry trace mới lưu các fact an toàn như stock, discount và shipping khi binary trả chúng về, không lưu prompt hoặc payload nhạy cảm.

## Trạng thái xác minh

- `python harness/selfcheck.py`: PASS.
- `python -m py_compile solution/wrapper.py`: PASS.
- Smoke test cho missing tool, missing total, PII cleanup và retry: PASS.
- Smoke test 8 thread cho single-flight cache: PASS, chỉ 1 agent call và 7 cache hit.
- Smoke test best-result selection: PASS.
- Chưa có public score mới cho cấu hình sau tối ưu; cần chạy lại public simulator và scorer để so sánh A/B với mốc 92,32.
