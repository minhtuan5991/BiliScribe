# BiliScribe 1.1.1

Dán link Bilibili → tải âm thanh → lưu MP3 → tạo transcript tiếng Trung tại máy.

## Cài và sử dụng

1. Mở `release\BiliScribe-Setup-1.1.1-x64.exe`, bấm **Tiếp theo → Cài đặt**. Có shortcut Start Menu, tùy chọn Desktop và mục gỡ trong Settings > Apps.
2. Dán link, mỗi dòng một video. Link có `?p=2` giữ đúng phần 2. Có thể chọn file MP3/M4A/WAV/MP4 trên máy.
3. Chọn chế độ và thư mục kết quả; có thể chọn `D:\Download-Transcript Bilibili\Ket-qua`.
4. Bấm **Bắt đầu tạo transcript**. Khi xong, dùng **Mở TXT**, **Nghe MP3**, **Đối chiếu** hoặc **Mở thư mục**.

Không cần cài Python, FFmpeg hoặc tạo tài khoản AI. Windows 10/11 x64. RAM 4 GB có thể dùng chế độ nhanh nếu còn khoảng 1 GB trống; 8 GB trở lên thuận tiện hơn. Chưa kiểm thử trên mọi loại CPU.

## Chọn chế độ

| Chế độ | Cách xử lý | Khi dùng |
|---|---|---|
| Tự động | CPU: SenseVoice có sẵn. GPU NVIDIA sẵn sàng: Large v3 hoặc Turbo theo VRAM | Sử dụng hằng ngày |
| Ưu tiên độ sát | Large v3 đầy đủ, beam 5, rồi đối chiếu SenseVoice độc lập | Cần tìm chỗ nhận dạng chưa chắc chắn |
| Cân bằng | Large v3 Turbo | Muốn xử lý nhanh hơn Large v3 trên GPU |
| Máy nhẹ / nhanh | SenseVoice Small INT8, CPU, có dấu câu | Máy ít RAM, không có NVIDIA, muốn dùng ngay |

Bộ cài **đóng sẵn mô hình SenseVoice khoảng 239 MB**. Chế độ nhanh nhận dạng file trên máy mà không cần mạng. Internet vẫn cần để tải video Bilibili. Các mô hình Whisper tải một lần khi được chọn: Tiny ~75 MB, Base ~145 MB, Small ~465 MB, Medium ~1,5 GB, Turbo ~1,6 GB, Large v3 ~3,1 GB.

Trong Nâng cao có thể chọn mô hình cụ thể; lựa chọn này ưu tiên hơn chế độ. Đối chiếu hai mô hình chỉ chạy khi dùng **Ưu tiên độ sát + Large v3**. SenseVoice chạy CPU INT8; Whisper trên NVIDIA dùng INT8/FP16. App giảm batch rồi chuyển CPU nếu GPU thiếu bộ nhớ, giữ nguyên mô hình đã chọn.

## File kết quả

- `audio.mp3`: để nghe lại, MP3 VBR chất lượng cao. Nhận dạng dùng audio nguồn, tránh thêm một vòng nén MP3.
- `transcript_zh.txt`: tiếng Trung UTF-8 BOM, mở bằng Notepad/Word.
- `transcript_zh.srt`: phụ đề có thời gian ước lượng.
- `transcript_zh.json`: từng đoạn, thời gian, thông tin mô hình và nhận dạng.
- `transcript_zh_review.txt`: đoạn cần nghe lại, dựa vào chỉ báo mô hình hoặc sai khác hai bản.
- `doi_chieu_zh.txt` và `.json`: những chỗ Large v3 và SenseVoice khác nhau, có mốc thời gian và ngữ cảnh. Có trong chế độ Ưu tiên độ sát + Large v3.
- `doi-chieu/`: bản SenseVoice độc lập dùng để kiểm tra bản chính.
- `checkpoint_zh.json`: điểm tiếp tục khi dừng.
- `result.json`: kết quả, thời gian hoàn tất, mô hình và số sai khác nếu có đối chiếu.

**Sai khác không chứng minh bản nào đúng.** Chữ số và cách viết số bằng chữ cũng có thể bị đánh dấu. App giữ nguyên bản chính, không tự ghép các câu hai mô hình và không dùng LLM để viết thêm nội dung. Hai mô hình có thể cùng nhận sai một từ; không có cờ cảnh báo cũng không bảo đảm chính xác.

SenseVoice có dấu câu và chuẩn hóa số nhưng vẫn nhầm từ đồng âm hoặc tên riêng. SenseVoice không cung cấp điểm độ tin cậy trong API đang dùng; JSON ghi `null` ở các trường này. Whisper có thể thiếu dấu câu. Chưa có transcript chuẩn được chép tay đầy đủ cho video mẫu nên không công bố tỷ lệ chính xác CER/WER.

Chọn giản thể/phồn thể/giữ nguyên kiểu chữ trong Nâng cao. Tên riêng/thuật ngữ gợi ý chỉ dùng với Whisper. Tắt VAD nếu giọng nhỏ bị bỏ sót. SRT và vùng nối giữa các đoạn vẫn cần kiểm tra khi dựng phụ đề chính xác.

## Tốc độ, GPU và video dài

SenseVoice dùng tối đa 4 luồng CPU; Whisper dùng tối đa 8 luồng, chừa tài nguyên cho giao diện. App tải trước tối đa hai video, nhận dạng tuần tự để hạn chế RAM. Whisper xử lý đoạn 5 phút với chồng lấn 2 giây; SenseVoice xử lý đoạn 28 giây với chồng lấn 1 giây. Ghép theo thời gian từ, lưu checkpoint sau từng đoạn.

Chạy lại cùng nguồn và cấu hình để tiếp tục phần đã lưu. Chọn Nhận dạng lại từ đầu để chạy lại. Lịch sử lưu ngay khi mỗi video xong, kể cả khi dừng cả hàng đợi sau đó. Điểm tiếp tục của bản 1.0 được làm lại khi chuyển sang 1.1 vì cơ chế nhận dạng đã thay đổi; file kết quả cũ vẫn còn.

NVIDIA cần driver tương thích CUDA 12. Nút **Chuẩn bị GPU NVIDIA** tải thư viện chính thức vào thư mục riêng (~1 GB tải, ~1,7 GB lưu), không cài driver hay CUDA Toolkit toàn hệ thống. AMD/Intel GPU dùng chế độ CPU. Large v3 có thể rất chậm trên CPU; dùng chế độ nhanh khi máy không đủ tài nguyên.

Tốc độ tải video phụ thuộc máy chủ Bilibili và mạng. Thời gian nhận dạng trong báo cáo kiểm thử không đồng nghĩa thời gian tải video; kết quả đo trên máy hiện tại không đại diện mọi máy.

Bản dịch tiếng Anh là tùy chọn chạy thêm một lượt; khi chọn SenseVoice/Turbo, app chuyển sang Large v3 để hỗ trợ dịch. Kết quả tiếng Anh lưu riêng.

## Video cần đăng nhập

Chọn Firefox hoặc file cookie Netscape của tài khoản có quyền xem. Chrome/Edge có thể chặn đọc cookie do mã hóa Windows. File cookie gốc không bị ghi đè. App không vượt khóa trả phí/tài khoản/DRM; audio không gửi đến dịch vụ AI.

## Lưu trữ và gỡ cài đặt

- Thư mục kết quả do bạn chọn. Mặc định Downloads\BiliScribe.
- Cài đặt, lịch sử, GPU runtime: `%LOCALAPPDATA%\BiliScribe`.
- Mô hình Whisper: `%LOCALAPPDATA%\BiliScribe\models`, có thể chuyển sang ổ D trong Nâng cao.
- SenseVoice đi kèm thư mục app, không nhân đôi vào cache.
- `.biliscribe-cache` trong thư mục kết quả giữ audio đã tải, giúp chạy lại nhanh. Có thể xóa sau khi app đã dừng nếu không cần tiếp tục.
- Gỡ app giữ lại kết quả, mô hình đã tải và cài đặt cá nhân.

Bộ cài tạo cục bộ, chưa ký chứng thư số; Windows có thể hiển thị nhà phát hành chưa xác định.

## Mã nguồn và build

`BUILD_WINDOWS.ps1` dùng Python 3.12 x64, PyInstaller và Inno Setup 6. Thư viện chốt phiên bản trong `requirements.txt` và `requirements-lock.txt`; `vendor/` gồm FFmpeg và SenseVoice đã kiểm tra SHA-256. Xem `THIRD_PARTY_NOTICES.md` để biết nguồn và giấy phép.

`python -m pytest tests -q` chạy kiểm thử logic. `BiliScribeWorker.exe --self-test <thư-mục>` kiểm tra bản đóng gói: DLL, checksum và suy luận SenseVoice, VAD, MP3, Unicode, giao diện và kiểm tra link.
