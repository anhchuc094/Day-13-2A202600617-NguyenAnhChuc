# Báo cáo phân tích private

## Trạng thái

- Đã nhận private simulator Linux đúng phase.
- Artifact hiện tại có `phase=private`, 80 QID `prv-*`, nhưng 80/80 `wrapper_error` và 80 `answer=null`.
- Telemetry xác nhận cả 80 lỗi là OpenRouter HTTP 402 `Insufficient credits`: key đã được gửi nhưng tài khoản/key không có credit. Agent chưa chạy nên không thể sinh answer.
- Chưa có private scorer trong workspace, nên chưa có headline/sub-score hợp lệ.

## Phát hiện injection

- Có 20/80 câu chứa `ORDER:` và `GHI CHU KHACH:`.
- Ghi chú chèn giá giả `1.000.000 VND` và yêu cầu bỏ qua giá hệ thống.
- Sanitizer cũ chỉ nhận `GHI CHÚ:`/`note:`, không nhận hậu tố `KHACH`, nên injection có thể lọt vào agent.

## Cải thiện đã thực hiện

- Mở rộng sanitizer cho `GHI CHU KHACH`, biến thể có dấu, `KHACH HANG`, `order note` và `note`.
- Loại prefix `ORDER:` nhưng giữ nguyên nội dung đơn hàng thật.
- Thêm regression test trên toàn bộ 20 câu injection; input sạch không còn note hoặc giá giả.
- Cập nhật finding `prompt_injection` với bằng chứng private và trace đại diện `prv-006`, `prv-011`, `prv-080`.
- Đổi system prompt sang tiếng Việt và bắt buộc mọi câu trả lời bằng tiếng Việt; giữ dòng cuối parseable `Tong cong: <số nguyên> VND`.
- Rút prompt tiếng Việt xuống dưới 600 ký tự để hạn chế bloat penalty.
- Wrapper không retry lỗi API vĩnh viễn 400/401/402/403/404, tránh nhân đôi request khi hết credit hoặc key sai.
- Script chạy không ghi đè output tốt khi 100% request lỗi; artifact lỗi được lưu riêng dưới tên `.failed-*`.

## Việc còn lại

- Nạp credit cho đúng tài khoản OpenRouter hoặc dùng key thuộc tài khoản còn credit, rồi chạy lại private.
- Khi có private scorer, tạo `score_private.json` và cập nhật score/telemetry.
- Chỉ tối ưu tiếp theo lỗi tổng quát có bằng chứng, không hardcode private question/answer.
