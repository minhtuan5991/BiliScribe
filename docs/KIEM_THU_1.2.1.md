# Kiểm thử BiliScribe 1.2.1

Thêm kiểm tra bản phát hành GitHub công khai mỗi lần mở app. Chạy ở luồng nền, không yêu cầu token, không tự cài đặt. Các chế độ ASR, tải audio, cài đặt và quy tắc ba file kết quả giữ nguyên.

- 65 kiểm thử tự động đạt: so sánh phiên bản, dữ liệu/URL không hợp lệ, giới hạn kích thước, mất mạng, thời hạn chờ, một kiểm tra mỗi lần mở, đóng app khi đang kiểm tra, giữ nguyên settings; cùng toàn bộ kiểm thử 1.2.0.
- Kết nối GitHub thật không dùng token: đọc được Release v1.2.0 và nhận ra bản mới khi giả định app đang ở 1.1.0.
- Bản 1.2.0 không có cơ chế kiểm tra cập nhật: cần cài 1.2.1 một lần để bắt đầu sử dụng tính năng này.

- EXE self-test đạt: nạp thư viện, mô hình SenseVoice, nhận dạng, FFmpeg, giao diện local/Pixazo và nút thông báo cập nhật giả lập 1.3.0 (không phải phiên bản đã phát hành).
- Worker EXE xử lý 60 giây audio tiếng Trung, dừng và chạy tiếp checkpoint đạt trong 11,86 giây; độ trễ dừng 0,31 giây, preview 451 ký tự; chỉ giữ ba file và xóa cache thành công.
- Cài 1.2.0 → nâng cấp 1.2.1 → self-test bản cài → gỡ cài đặt thử nghiệm: tất cả đạt, không cần khởi động lại Windows.
- Kiểm tra trực quan thông báo cập nhật ở cửa sổ 960×690: nút có đủ nhãn, không che tác vụ chính.

Không thực hiện thêm yêu cầu Pixazo tính credit cho thay đổi này. Không thay đổi các module tải audio, nhận dạng, Pixazo, config hay quy tắc dọn kết quả. Bộ cài chưa ký số. GitHub có thể giới hạn tần suất; app ghi Nhật ký và thử lại ở lần mở sau.
