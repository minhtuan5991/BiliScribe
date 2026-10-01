# Kiểm thử BiliScribe 1.2.3 

Đổi tên hai file transcript theo tên Việt không dấu sau khi hoàn tất. Giữ nguyên file đối chiếu, nội dung, cấu hình và nhận dạng.

81 kiểm thử tự động đạt: bỏ dấu, đ/Đ, Unicode tổ hợp, giữ nguyên byte nội dung, tránh ghi đè, hoàn tác khi đổi tên file thứ hai thất bại, giới hạn đường dẫn, mở/preview tên cũ và mới, cùng toàn bộ kiểm thử trước.

Báo cáo kiểm thử cho Release 1.2.3.

- Worker EXE: nhận dạng 60 giây audio tiếng Trung, dừng rồi chạy tiếp từ checkpoint, hoàn tất trong 16,48 giây; độ trễ dừng 0,33 giây.
- Kết quả thực tế đúng tên `Nhung cau chuyen ky la ve luat le_zh.txt` và `.srt`, cùng `doi_chieu_zh.txt`. Thư mục Việt–Trung giữ nguyên, preview 451 ký tự, các nút mở file hoạt động, nguồn được giữ và cache được dọn.

- Bộ cài: cài 1.2.2 → nâng cấp 1.2.3 → self-test bản cài → gỡ thử nghiệm đều đạt.
- ZIP mã nguồn và SHA-256 bộ cài đã kiểm tra.
