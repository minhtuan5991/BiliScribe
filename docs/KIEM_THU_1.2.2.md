# Kiểm thử BiliScribe 1.2.2

Thay đổi: tên thư mục hoàn tất theo mẫu Tên tiếng Việt - Tên tiếng Trung, lọc mã và nhãn quảng bá, tránh ghi đè. Không thay đổi nhận dạng hay cài đặt.

Kiểm thử bao gồm làm sạch tiêu đề, giữ số tập/tên chính, ví dụ người dùng, dịch/cache/mất mạng/hủy, giới hạn đường dẫn, tên trùng và không đổi tên tác vụ chưa hoàn tất. Kết nối dịch thật đã thử với hai tiêu đề mẫu; không gửi audio hoặc transcript.

Xem báo cáo phát hành kèm bộ cài để biết kết quả kiểm thử EXE/nâng cấp. Không gọi thêm Pixazo tính credit.

## Kết quả

- 76 kiểm thử tự động đạt (gồm toàn bộ kiểm thử 1.2.1).
- Worker EXE với 60 giây tiếng Trung: dừng sau checkpoint rồi chạy tiếp thành công, 16,56 giây toàn lượt, độ trễ dừng 0,33 giây.
- Thư mục thực tế: `Những câu chuyện kỳ lạ về luật lệ - 规则怪谈`; đúng ba file TXT/SRT/đối chiếu, cache được dọn, nguồn giữ nguyên.
- Lịch sử trỏ đúng thư mục sau đổi tên; preview 451 ký tự, các nút mở kết quả hoạt động.
- Đã dịch thật hai tên mẫu bằng endpoint web Google Translate. Chất lượng bản dịch máy không được đảm bảo như biên dịch thủ công; mất mạng/giới hạn dịch vụ sẽ lưu tên Trung sạch và ghi Nhật ký.

Bộ cài chưa ký số. Không thêm dependency hay thay đổi cài đặt cũ.
