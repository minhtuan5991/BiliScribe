# Đọc và kết hợp hai ứng dụng gốc

BiliDownloader.py: Tkinter, yt-dlp, FFmpeg; tải nhiều link, chọn định dạng, cookie trình duyệt, song song và nhiều lần retry. Hàm normalize_url bỏ toàn bộ query nên làm mất phần p= của video nhiều phần.

TranscriptTool.py: Tkinter, faster-whisper, CPU INT8/GPU FP16, TXT/SRT/JSON, tiếng Trung + dịch Anh. process_file tạo Transcriber mới cho mỗi file. Mặc định chạy cả CN và EN, tốn thêm lượt suy luận. Prompt mặc định chứa từ vựng tận thế/nhân vật nên không phù hợp mọi chủ đề. Bộ cài thực chất là batch tạo Python venv và cài gói; máy khác cần Python phù hợp.

BiliScribe triển khai lại một luồng thống nhất với GUI Qt, worker độc lập, tải trước tối đa 2 video, mô hình được giữ trong toàn lượt xử lý, transcript Trung mặc định, giữ p=, audio-only tải trước MP3, nhận dạng trên audio gốc, chunk có overlap ở cấp từ, checkpoint, CPU INT8/GPU INT8_FP16 và fallback, không gán sẵn thể loại nội dung.

Cài đặt Windows dùng PyInstaller onedir + Inno Setup per-user, Start Menu/Desktop shortcut và uninstaller. Không cần cài Python riêng. Chỉ mô hình AI và runtime GPU tùy chọn được tải sau.

Giới hạn: chưa benchmark nhiều cấu hình máy; chưa có transcript do người kiểm chuẩn để tính CER/WER. Kết quả kiểm thử xác minh pipeline, thời gian trên máy hiện tại, định dạng đầu ra và tính ổn định; không phải chứng minh chính xác tuyệt đối.
