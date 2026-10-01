# BiliScribe 1.2.3

Dán link Bilibili → tải âm thanh → tạo transcript tiếng Trung trên máy hoặc qua Pixazo API.

## Cài và sử dụng

1. Mở `release\BiliScribe-Setup-1.2.3-x64.exe`, bấm **Tiếp theo → Cài đặt**. Có shortcut Start Menu, tùy chọn Desktop và mục gỡ trong Settings > Apps.
2. Dán link, mỗi dòng một video. Link có `?p=2` giữ đúng phần 2. Có thể chọn file MP3/M4A/WAV/MP4 trên máy.
3. Chọn chế độ và thư mục kết quả; có thể chọn `D:\Download-Transcript Bilibili\Ket-qua`.
4. Bấm **Bắt đầu tạo transcript**. Khi xong, dùng **Mở TXT**, **Mở SRT**, **Đối chiếu** hoặc **Mở thư mục**.

Không cần cài Python, FFmpeg hoặc tạo tài khoản AI. Windows 10/11 x64. RAM 4 GB có thể dùng chế độ nhanh nếu còn khoảng 1 GB trống; 8 GB trở lên thuận tiện hơn. Chưa kiểm thử trên mọi loại CPU.

## Chọn chế độ

| Chế độ | Cách xử lý | Khi dùng |
|---|---|---|
| Tự động | CPU: SenseVoice có sẵn. GPU NVIDIA sẵn sàng: Large v3 hoặc Turbo theo VRAM | Sử dụng hằng ngày |
| Ưu tiên độ sát | Large v3 đầy đủ, beam 5, rồi đối chiếu SenseVoice độc lập | Cần tìm chỗ nhận dạng chưa chắc chắn |
| Cân bằng | Large v3 Turbo | Muốn xử lý nhanh hơn Large v3 trên GPU |
| Máy nhẹ / nhanh | SenseVoice Small INT8, CPU, có dấu câu | Máy ít RAM, không có NVIDIA, muốn dùng ngay |
| Pixazo API | Qwen ASR Realtime, 1–4 đoạn song song | Dùng API key Pixazo, không cần GPU / tải mô hình |

Bộ cài **đóng sẵn mô hình SenseVoice khoảng 239 MB**. Chế độ nhanh nhận dạng file trên máy mà không cần mạng. Internet vẫn cần để tải video Bilibili. Các mô hình Whisper tải một lần khi được chọn: Tiny ~75 MB, Base ~145 MB, Small ~465 MB, Medium ~1,5 GB, Turbo ~1,6 GB, Large v3 ~3,1 GB.

Trong Nâng cao có thể chọn mô hình cụ thể; lựa chọn này ưu tiên hơn các chế độ chạy trên máy. Pixazo API dùng Qwen riêng; các thiết lập thiết bị/mô hình cục bộ được giữ nhưng không áp dụng. Đối chiếu hai mô hình chỉ chạy khi dùng **Ưu tiên độ sát + Large v3**. SenseVoice chạy CPU INT8; Whisper trên NVIDIA dùng INT8/FP16. App giảm batch rồi chuyển CPU nếu GPU thiếu bộ nhớ, giữ nguyên mô hình đã chọn.

## Luồng Pixazo API

1. Chọn **Pixazo API · Qwen tiếng Trung** trong Chế độ.
2. Nhập API key; chọn 1–4 luồng (mặc định 3). Key chỉ được nhớ nếu chọn checkbox, mã hóa bằng Windows DPAPI cho tài khoản hiện tại. Bỏ chọn sẽ xóa khóa đã nhớ. Key không nằm trong settings, file công việc, nhật ký, transcript hay bộ cài.
3. Dán link Bilibili hoặc thêm file trên máy rồi bấm Bắt đầu như trước.

Âm thanh được gửi tới `asr-stream.pixazo.ai` qua kết nối mã hóa. Cần mạng và tài khoản còn credit; mỗi kết nối giữ một phần số dư tạm thời. Giảm số luồng khi bị giới hạn kết nối hoặc không đủ số dư. Không tự đổi sang API từ các chế độ cục bộ.

Để tăng tốc, app không nạp mô hình cục bộ / khởi tạo GPU trong chế độ này. Các đoạn cân bằng theo độ dài video, ưu tiên cắt tại khoảng lặng; gửi đồng thời tối đa số luồng đã chọn, mỗi phiên khoảng 5 phút trở xuống. Dữ liệu PCM được đọc từng khung, không nạp toàn bộ video vào RAM. API Realtime cần truyền gần thời gian thực; tốc độ thực tế còn phụ thuộc mạng, dịch vụ và số luồng.

Các đoạn hoàn tất được lưu riêng, ghép đúng thứ tự dù phản hồi về khác thứ tự. Dừng/lỗi giữ tiến độ. Chạy tiếp không gửi lại các đoạn đã xong; đoạn đang gửi khi mất mạng có thể phải gửi lại và phát sinh phí lần nữa. App chỉ tự thử lại có giới hạn ở bước mở phiên trước khi gửi audio, không tự gửi lại toàn bộ đoạn sau lỗi giữa chừng.

Luồng này cố định nhận dạng tiếng Trung, không dịch hoặc viết lại nội dung. Có thể chọn giản thể/phồn thể/giữ nguyên. Không dùng tùy chọn từ vựng gợi ý và VAD cục bộ; Pixazo xử lý phát hiện lời nói trên máy chủ. SRT dựa vào sự kiện lời nói; khi thiếu mốc chi tiết, thời gian được ước lượng. `doi_chieu_zh.txt` ghi rõ chưa đối chiếu với mô hình thứ hai.

Tài liệu nhà cung cấp: https://www.pixazo.ai/models/qwen-audio

## File kết quả

Khi hoàn tất thành công, mỗi video chỉ còn đúng ba file:

- `Ten tieng Viet_zh.txt`: bản chép lời tiếng Trung; tên file lấy từ tên Việt không dấu.
- `Ten tieng Viet_zh.srt`: phụ đề có thời gian ước lượng.
- `doi_chieu_zh.txt`: sai khác Large v3 / SenseVoice khi chạy Ưu tiên độ sát + Large v3. Chế độ khác ghi rõ chưa đối chiếu hai mô hình, kèm các đoạn cần kiểm tra nếu có.

MP3, JSON, bản đối chiếu trung gian, checkpoint và âm thanh tải tạm được xóa sau khi hoàn tất. Khi dừng hoặc gặp lỗi, chúng được giữ để chạy tiếp. File nguồn người dùng chọn trên máy, mô hình AI và lịch sử ứng dụng được giữ nguyên. Quy tắc áp dụng cho các lần xử lý bằng bản 1.2.1; không tự quét xóa kết quả cũ.

Các hộp chọn không đổi lựa chọn khi lăn chuột, kể cả đang có tiêu điểm. Dùng nhấp chuột hoặc bàn phím để chọn.

**Sai khác không chứng minh bản nào đúng.** Chữ số và cách viết số bằng chữ cũng có thể bị đánh dấu. App giữ nguyên bản chính, không tự ghép các câu hai mô hình và không dùng LLM để viết thêm nội dung. Hai mô hình có thể cùng nhận sai một từ; không có cờ cảnh báo cũng không bảo đảm chính xác.

SenseVoice có dấu câu và chuẩn hóa số nhưng vẫn nhầm từ đồng âm hoặc tên riêng. SenseVoice không cung cấp điểm độ tin cậy trong API đang dùng. Whisper có thể thiếu dấu câu. Chưa có transcript chuẩn được chép tay đầy đủ cho video mẫu nên không công bố tỷ lệ chính xác CER/WER.

Chọn giản thể/phồn thể/giữ nguyên kiểu chữ trong Nâng cao. Tên riêng/thuật ngữ gợi ý chỉ dùng với Whisper. Tắt VAD nếu giọng nhỏ bị bỏ sót. SRT và vùng nối giữa các đoạn vẫn cần kiểm tra khi dựng phụ đề chính xác.

## Tốc độ, GPU và video dài

SenseVoice dùng tối đa 4 luồng CPU; Whisper dùng tối đa 8 luồng, chừa tài nguyên cho giao diện. App tải trước tối đa hai video, nhận dạng tuần tự để hạn chế RAM. Whisper xử lý đoạn 5 phút với chồng lấn 2 giây; SenseVoice xử lý đoạn 28 giây với chồng lấn 1 giây. Ghép theo thời gian từ, lưu checkpoint sau từng đoạn.

Sau khi dừng giữa chừng, chạy lại cùng nguồn và cấu hình để tiếp tục phần đã lưu. Một video đã hoàn tất sẽ phải tải và nhận dạng lại nếu chạy lần nữa vì dữ liệu tạm đã được xóa. Chọn Nhận dạng lại từ đầu để chạy lại. Lịch sử lưu ngay khi mỗi video xong, kể cả khi dừng cả hàng đợi sau đó. Điểm tiếp tục của bản 1.0 được làm lại khi chuyển sang 1.1 vì cơ chế nhận dạng đã thay đổi; file kết quả cũ vẫn còn.

NVIDIA cần driver tương thích CUDA 12. Nút **Chuẩn bị GPU NVIDIA** tải thư viện chính thức vào thư mục riêng (~1 GB tải, ~1,7 GB lưu), không cài driver hay CUDA Toolkit toàn hệ thống. AMD/Intel GPU dùng chế độ CPU. Large v3 có thể rất chậm trên CPU; dùng chế độ nhanh khi máy không đủ tài nguyên.

Tốc độ tải video phụ thuộc máy chủ Bilibili và mạng. Thời gian nhận dạng trong báo cáo kiểm thử không đồng nghĩa thời gian tải video; kết quả đo trên máy hiện tại không đại diện mọi máy.

Bản này chỉ xuất ba file tiếng Trung; tùy chọn dịch tiếng Anh và lưu âm thanh đã được bỏ khỏi giao diện.

## Video cần đăng nhập

Chọn Firefox hoặc file cookie Netscape của tài khoản có quyền xem. Chrome/Edge có thể chặn đọc cookie do mã hóa Windows. File cookie gốc không bị ghi đè. App không vượt khóa trả phí/tài khoản/DRM; các chế độ chạy trên máy không gửi audio tới dịch vụ AI; chế độ Pixazo gửi âm thanh tới Pixazo theo lựa chọn của bạn.

## Lưu trữ và gỡ cài đặt

- Thư mục kết quả do bạn chọn. Mặc định Downloads\BiliScribe.
- Cài đặt, lịch sử, GPU runtime: `%LOCALAPPDATA%\BiliScribe`.
- Mô hình Whisper: `%LOCALAPPDATA%\BiliScribe\models`, có thể chuyển sang ổ D trong Nâng cao.
- SenseVoice đi kèm thư mục app, không nhân đôi vào cache.
- `.biliscribe-cache` chỉ giữ audio của công việc đang chạy hoặc chưa hoàn tất. Dữ liệu của công việc thành công được dọn sau khi các luồng tải đã đóng file.
- Gỡ app giữ lại kết quả, mô hình đã tải và cài đặt cá nhân.

Bộ cài tạo cục bộ, chưa ký chứng thư số; Windows có thể hiển thị nhà phát hành chưa xác định.

## Mã nguồn và build

`BUILD_WINDOWS.ps1` dùng Python 3.12 x64, PyInstaller và Inno Setup 6. Thư viện chốt phiên bản trong `requirements.txt` và `requirements-lock.txt`; `vendor/` gồm FFmpeg và SenseVoice đã kiểm tra SHA-256. Xem `THIRD_PARTY_NOTICES.md` để biết nguồn và giấy phép.

`python -m pytest tests -q` chạy kiểm thử logic. `BiliScribeWorker.exe --self-test <thư-mục>` kiểm tra bản đóng gói: DLL, checksum và suy luận SenseVoice, VAD, MP3, Unicode, giao diện và kiểm tra link.

## Kiểm tra cập nhật (từ 1.2.1)

Mỗi lần mở app, BiliScribe kiểm tra bản phát hành ổn định mới nhất trên GitHub ở luồng nền. Khi có bản mới, nút **Có bản … / Mở trang tải** xuất hiện ở thanh bên trái. Bấm nút để mở trang phát hành, tải bộ cài rồi đóng app trước khi cài nâng cấp. App không tự tải hay tự chạy bộ cài.

Không cần token GitHub. Yêu cầu kiểm tra chỉ gửi thông tin phiên bản app, không gửi âm thanh, transcript hoặc key Pixazo. Mất mạng, GitHub giới hạn truy cập hoặc lỗi phản hồi sẽ được ghi trong Nhật ký; bạn vẫn dùng app bình thường và lần mở tiếp theo app sẽ kiểm tra lại. Cài đặt và mô hình đã lưu được giữ nguyên.

## Tên thư mục kết quả (từ 1.2.2)

Sau khi xử lý thành công, thư mục mang tên **Tên tiếng Việt - Tên tiếng Trung**, ví dụ `Những câu chuyện kỳ lạ về luật lệ - 规则怪谈`. App bỏ mã BV/mã nội bộ ở cuối, emoji, ký tự ẩn, hashtag và các nhãn quảng bá đã nhận diện như `【完结短剧】`, `【恐怖怪谈】`, `完整版`. Các từ có thể thuộc tên truyện và số tập được giữ lại. Tiêu đề quá dài được rút gọn để tương thích đường dẫn Windows.

Chỉ tiêu đề đã làm sạch được gửi đến endpoint web Google Translate để dịch sang Việt, không gửi audio/transcript/API key. Không cần nhập thêm key. Bản dịch máy có thể chưa đúng sắc thái; endpoint web không có cam kết ổn định như Cloud Translation API. Dịch có giới hạn chờ 5 giây và lưu cache cục bộ để tái sử dụng. Khi mất mạng/dịch thất bại, app giữ tên Trung sạch và ghi lý do vào Nhật ký; transcript vẫn được lưu.

Tên trùng thêm `(2)`, `(3)`; không ghi đè thư mục cũ. Tác vụ dở vẫn giữ tên nội bộ/checkpoint để tiếp tục, chỉ đổi tên sau khi hoàn tất và dọn còn ba file. Không tự đổi tên kết quả đã tạo bởi bản cũ. Mọi chế độ CPU/GPU/Pixazo và cài đặt hiện có được giữ nguyên.

## Tên file hoàn tất (từ 1.2.3)

Hai file transcript dùng tên Việt không dấu, có đuôi `_zh.txt` và `_zh.srt`. Ví dụ: `Nhung cau chuyen ky la ve luat le_zh.txt` và `Nhung cau chuyen ky la ve luat le_zh.srt`. File đối chiếu vẫn là `doi_chieu_zh.txt`, tổng cộng ba file. Chữ đ/Đ được chuyển thành d/D, dấu tiếng Việt và dấu câu không phù hợp được bỏ; tên dài được rút gọn theo giới hạn đường dẫn Windows.

Chỉ đổi tên sau khi hoàn tất; không thay đổi nội dung tiếng Trung, mốc SRT hay checkpoint. Các nút Mở TXT/SRT và preview đọc được cả tên cũ lẫn tên mới. Nếu chưa có bản dịch, dùng phần tên gốc có thể chuyển thành chữ Latin; nếu không có, dùng `Video_zh.txt` / `Video_zh.srt` và Nhật ký báo chưa dịch được tên. Không tự đổi tên kết quả cũ.

Bản 1.2.3 được phát hành trên GitHub; tải bộ cài từ trang Releases.
