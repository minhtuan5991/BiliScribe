# BiliScribe

Ứng dụng Windows tải âm thanh Bilibili và tạo transcript tiếng Trung bằng CPU/GPU hoặc Pixazo API.

**Phiên bản hiện tại: 1.2.0**

- [Tải bộ cài Windows](https://github.com/minhtuan5991/BiliScribe/releases/latest)
- [Hướng dẫn tiếng Việt](README_VI.md)
- [Báo cáo kiểm thử 1.2.0](docs/KIEM_THU_1.2.0.md)

## Tính năng

- Link Bilibili hoặc file audio/video trên máy.
- SenseVoice CPU, Whisper Large v3/Turbo với CPU/GPU và chế độ đối chiếu.
- Pixazo Qwen ASR Realtime, tối đa 4 đoạn song song, lưu tiến độ và chạy tiếp.
- Khi hoàn tất chỉ giữ `transcript_zh.txt`, `transcript_zh.srt`, `doi_chieu_zh.txt`.
- Hộp chọn không đổi lựa chọn khi cuộn chuột.
- API key do người dùng nhập, tùy chọn mã hóa bằng Windows DPAPI; không đóng kèm key.

## Build trên Windows

Kho Git không chứa FFmpeg EXE và mô hình ONNX lớn. Tải `BiliScribe-Source-1.2.0.zip` từ Release v1.2.0; lấy thư mục `vendor` trong ZIP đặt vào thư mục dự án. Gói ZIP gồm mã nguồn và các tài nguyên nhị phân cần thiết cho phiên bản này.

Cần Python 3.12 x64 và Inno Setup 6. Chạy:

```powershell
.\BUILD_WINDOWS.ps1 -Python python -Compiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

Mô hình Whisper lớn chỉ tải khi người dùng chọn chế độ tương ứng. Gói phát hành có SenseVoice dùng ngay trên CPU.

## Kiểm thử và giới hạn

Bản 1.2.0 có 49 kiểm thử tự động đạt; đã thử EXE với Pixazo thật (90 giây audio, 3 kết nối, khoảng 47 giây xử lý), CPU dừng/chạy tiếp, cài đặt/nâng cấp/gỡ. Mốc SRT có thể là ước lượng; chưa công bố CER/WER. Bộ cài chưa ký số.

Phần tải Bilibili của 1.2.0 vẫn dùng yt-dlp; chưa bổ sung tải nhiều HTTP Range song song. Tốc độ tải phụ thuộc nguồn và đường truyền.

Xem [nguồn và giấy phép thành phần](THIRD_PARTY_NOTICES.md). Kho không kèm dữ liệu cá nhân, cookie, key hoặc kết quả video thử.
