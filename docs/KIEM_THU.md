# Kiểm thử BiliScribe

Máy chạy kiểm thử: Windows 64-bit, RAM khoảng 11,7 GB, CPU 8 nhân vật lý, NVIDIA RTX 3050 Laptop 6 GB. RAM trống lúc kiểm thử khoảng 2–3 GB.

Video người dùng cung cấp: https://www.bilibili.com/video/BV1sDLG6DED3/?p=1
Tên: 【完结短剧】极寒末世：重生后我改造核航母当堡垒
Thời lượng: 535,68 giây.

Kiểm thử source thực tế:
- Tải được âm thanh và xuất MP3.
- Large v3 Turbo CPU INT8 chạy thành công trên 75 giây đầu; tổng lượt 106,4 giây, có gồm tải mô hình lần đầu nên không dùng để so tốc độ CPU/GPU.
- Large v3 đầy đủ GPU INT8_FP16 chạy hết video, 369 đoạn tiếng Trung; tổng 156,8 giây. Audio cache đã có, thời gian tải video không nằm trong con số này; lượt này có chuẩn bị mô hình.
- Đã kiểm tra đầu ra TXT, SRT, JSON, checkpoint và Unicode.
- 13 kiểm thử logic đã qua: URL/phần video, URL giả mạo, profile theo bộ nhớ, Unicode/timing, hủy, fallback GPU, tiếp tục checkpoint và ghép phần chồng lấn ở cấp từ.
- Self-test GUI đã qua ở 1280x860 và 960x690, có kiểm tra trường trống, link sai và hiển thị chữ Trung.

Chưa có bản chép tay đã kiểm chuẩn để tính CER/WER. Các thời gian trên chỉ mô tả một lượt trên máy này, không bảo đảm tốc độ ở máy khác. Trong mẫu còn có khả năng nhầm đồng âm / thuật ngữ. Đây là xác minh chức năng và hiệu năng quan sát được, không phải chứng nhận transcript đúng 100%.

Kết quả kiểm thử bản EXE và bộ cài được ghi bổ sung trong PACKAGED_TESTS.json sau khi đóng gói.

Bản EXE độc lập đã xử lý toàn bộ video thành công: 175,9 giây với Large v3, GPU INT8_FP16; audio và model đã có trong cache. Mốc thời gian tăng dần, kết thúc tại 535.32 giây.

Kiểm thử giao diện + worker: nhận JSON, gắn Windows Job Object, bấm dừng và kết thúc trong 3,62 giây, không cần đóng cưỡng bức từ bên ngoài.

Bộ cài: cài thành công (exit 0), tạo mục gỡ cài đặt; EXE sau khi cài chạy self-test thành công (exit 0). Gỡ cài đặt thành công (exit 0), gỡ executable và mục registry; không yêu cầu khởi động lại.

Giao diện chạy lại cùng cấu hình: dùng checkpoint, đọc 3.636 ký tự preview trong 2,66 giây, báo 1 thành công / 0 lỗi và mở khóa lại các nút.
