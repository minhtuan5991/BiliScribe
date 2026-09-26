# Phát hành bản cập nhật

BiliScribe từ 1.2.1 đọc `https://api.github.com/repos/minhtuan5991/BiliScribe/releases/latest` mỗi lần mở giao diện. Kho cần công khai; không nhúng GitHub token vào app.

Để phát hành bản tiếp theo:

1. Tăng phiên bản dạng `major.minor.patch` trong app, spec và installer; cập nhật hướng dẫn, chạy kiểm thử và tạo bộ cài.
2. Đẩy mã nguồn đã kiểm tra, tạo tag `vX.Y.Z` và tạo GitHub Release ở chế độ draft.
3. Tải lên bộ cài, mã nguồn và checksum. Kiểm tra đủ tài sản rồi xuất bản release ổn định và đánh dấu latest.
4. Kiểm tra endpoint trên trả đúng `tag_name` và `html_url`. Lần mở app kế tiếp sẽ thông báo bản mới.

Không dùng prerelease/draft làm bản cập nhật ổn định. App chỉ mở trang phát hành khi người dùng bấm nút; không tự tải hoặc chạy EXE. Không cần sửa feed riêng mỗi lần phát hành.

Xử lý mạng nằm trong daemon thread không gọi Qt. GUI thăm dò queue mỗi 150 ms, hết chờ sau 12 giây; socket timeout 8 giây, đọc tối đa 256 KiB. Không ghi settings, token hoặc dữ liệu transcript vào yêu cầu. Khi đóng app không chờ network thread. Lỗi mạng/giới hạn GitHub chỉ ghi thông báo chung vào Nhật ký.
