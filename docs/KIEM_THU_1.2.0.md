# BiliScribe 1.2.0 — kết quả kiểm thử

Ngày: 25/09/2026. Bản mới thêm Pixazo Qwen ASR Realtime và giữ các chế độ cục bộ của 1.1.2.

## Thay đổi

- Thêm chế độ Pixazo API, nhập API key, tùy chọn nhớ key bằng Windows DPAPI và 1–4 luồng (mặc định 3).
- Luồng API không khởi tạo GPU hay tải mô hình AI cục bộ. Chia đoạn cân bằng theo độ dài, ưu tiên khoảng lặng, stream PCM theo khung thay vì đọc toàn bộ video vào RAM.
- Mỗi đoạn hoàn tất được checkpoint riêng. Ghép đúng thứ tự, chạy tiếp bỏ qua đoạn đã hoàn tất, chỉ thử lại có giới hạn khi chưa gửi âm thanh.
- Chờ sự kiện transcript hoàn tất; không lấy bản tạm làm kết quả cuối. Đã sửa tương thích lỗi commit bộ đệm rỗng khi VAD máy chủ tự kết thúc câu.
- Vẫn chỉ giữ transcript_zh.txt, transcript_zh.srt và doi_chieu_zh.txt sau thành công; dữ liệu tạm được giữ khi dừng/lỗi. Luồng API ghi rõ chưa đối chiếu với mô hình thứ hai.
- Tất cả hộp chọn vẫn không đổi giá trị khi lăn chuột. CPU/GPU, tải Bilibili, lịch sử và nút dừng/chạy tiếp vẫn có.

## Kiểm thử đã thực hiện

- 49 kiểm thử tự động đạt: các logic cũ; giao thức WebSocket qua máy chủ thử cục bộ; thứ tự sự kiện và kết quả về khác thứ tự; partial/final; timeout chờ final; hủy stream; lỗi 401/402/403/429/503; checkpoint/chạy tiếp; mã hóa khóa; dọn file; thao tác hộp chọn.
- Pixazo thật: đoạn 8 giây nhận dạng thành công sau sửa tương thích. Các lượt chẩn đoán trước đó có lỗi giao thức commit/kết nối, không tính là kết quả đạt.
- EXE Pixazo thật: 90 giây đầu video BV1sDLG6DED3, 3 kết nối, 47.22 giây tính từ lúc khởi động worker. Audio đã tải sẵn, không bao gồm tải video. Có 19 cue SRT, mốc cuối 90.0 giây, thứ tự mốc tăng dần. Chỉ còn 3 file và cache đã được xóa. Đây là phép đo một lượt, không cam kết tốc độ cho mọi mạng/video.
- GUI + EXE CPU: dừng trong 0.44 giây, giữ checkpoint, chạy tiếp từ phần đã lưu, hoàn tất và chỉ còn 3 file. Preview có 451 ký tự, các nút mở file hoạt động theo trạng thái.
- Bộ cài: cài 1.1.2 → nâng cấp 1.2.0 → self-test → gỡ bản thử, tất cả mã thoát 0. Đúng version, EXE và mục đăng ký bản thử được gỡ.
- Self-test bản cài đạt DLL, checksum/suy luận SenseVoice, FFmpeg, VAD, OpenCC, WebSocket, UI thường/nhỏ/nâng cao/Pixazo, kiểm tra thiếu key và nguồn không hợp lệ.
- ZIP mã nguồn CRC đạt, 118 file; có mô-đun API và kiểm thử, không chứa verification, reference, venv, file khóa DPAPI hoặc literal key hex 32 ký tự trong Python.
- Key thật chỉ truyền tới tiến trình worker qua môi trường và header TLS của Pixazo. Kiểm thử xác nhận key không xuất hiện trong request JSON, stderr hay event log. Không có key thật trong mã nguồn/bộ cài.

## Giới hạn

Chưa có transcript chuẩn chép tay để đo CER/WER. Kết quả API mẫu vẫn có thể nhầm từ đồng âm và tên riêng. SRT Realtime dựa vào ranh giới lời nói; các câu dài được chia thời gian theo độ dài chữ, chưa phải căn chỉnh từng từ. Cần kiểm tra khi dựng phụ đề chính xác.

Live API đã thử đến 90 giây; checkpoint song song và lỗi mạng được kiểm thử có kiểm soát trên máy, chưa thử hàng giờ trên dịch vụ thật. Không công bố mức phí thực trả vì không đọc lịch sử thanh toán Pixazo. API cần key và credit riêng của người dùng; số luồng ảnh hưởng hạn mức kết nối và tiền giữ tạm thời. Các chế độ cục bộ không tự chuyển sang API.

Bộ cài chưa ký chứng thư số.

## Bàn giao

- `BiliScribe-Setup-1.2.0-x64.exe` — 371,021,871 byte.
- SHA-256: `77c2c225fada829db5c4085c8b8c330ce47df11e661d65771c77df7dde42f5f2`.
- `BiliScribe-Source-1.2.0.zip`: mã nguồn.
- `Mau-1.2.0-Pixazo-90s`: đúng ba file kết quả thử API.
- `Giao-dien-1.2.0-Pixazo.png`: ảnh giao diện không chứa khóa.
- `PACKAGED_TESTS-1.2.0.json`: chi tiết kiểm thử.

Tài liệu API đã đối chiếu: https://www.pixazo.ai/models/qwen-audio
Thư viện WebSocket: https://websockets.readthedocs.io/en/latest/reference/asyncio/client.html
