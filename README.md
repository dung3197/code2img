# Code2Img

Code2Img chuyển một tệp hoặc cả thư mục mã nguồn qua ảnh QR. Máy nhận có thể khôi phục cấu trúc thư mục, thư mục rỗng và từng byte của tệp, kể cả tệp nhị phân. Sau khi cài đặt, việc tạo và đọc ảnh có thể thực hiện ngoại tuyến.

## Cài đặt

Cần Python 3.10 trở lên. Chạy các lệnh sau trong thư mục dự án trên máy tạo ảnh và máy chạy chức năng nhận ảnh.

**Linux và macOS**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

Trên PowerShell, dùng `.\.venv\Scripts\code2img.exe` thay cho `code2img` trong các ví dụ bên dưới.

## Tạo ảnh QR

```bash
code2img pack ./ma-nguon -o ./qr-output
```

Thay `./ma-nguon` bằng đường dẫn đến tệp hoặc thư mục cần chuyển. Chọn thư mục đầu ra chưa tồn tại và đặt nó ngoài thư mục nguồn nếu sẽ đóng gói lại cùng nguồn.

| Đầu ra | Nội dung |
| --- | --- |
| `project.png` | Ảnh tổng hợp chứa một QR nếu bản ZIP có tối đa 1.600 byte, hoặc một lưới QR có viền xanh nếu bản ZIP lớn hơn. |
| `parts/` | Bộ ảnh QR đánh số, dùng để khôi phục từ từng ảnh riêng. |
| `source-tree.txt` | Cây thư mục đã đóng gói và số QR tương ứng trong `parts/`. |

## Khôi phục mã nguồn

**Bằng dòng lệnh**

```bash
code2img unpack ./qr-output/project.png -o ./ma-nguon-khoi-phuc
```

Để dùng bộ ảnh riêng, chạy `code2img unpack ./qr-output/parts -o ./ma-nguon-tu-anh-rieng`. Lệnh cũng nhận nhiều đường dẫn ảnh theo thứ tự bất kỳ. Hãy chọn thư mục đích chưa tồn tại. Code2Img báo các phần còn thiếu và kiểm tra SHA-256 trước khi giải nén.

**Bằng trình duyệt**

1. Trên máy nhận, chạy `code2img serve` và mở <http://127.0.0.1:8765>.
2. Dán ảnh vào trang hoặc bấm **Chọn ảnh** hay **Chụp ảnh**. Khi chụp ảnh tổng hợp có lưới, giữ đủ bốn cạnh màu xanh trong khung hình. Nếu trang báo lưới còn thiếu phần, chọn các ảnh mang số tương ứng trong `parts/`.
3. Khi đã nhận đủ các phần, bấm **Tải ZIP** để tải `code2img.zip`, rồi giải nén.

Để mở trang từ điện thoại cùng mạng nội bộ, chạy `code2img serve --host 0.0.0.0` trên máy nhận rồi mở `http://<IP-máy-nhận>:8765` trên điện thoại.

## Tùy chọn đóng gói

| Tùy chọn | Khi nào dùng |
| --- | --- |
| `--format jpeg` hoặc `--format webp` | Xuất ảnh `.jpg` hoặc `.webp` thay cho PNG mặc định. |
| `--part-size 256` | Giảm mật độ của từng QR riêng. Giá trị hợp lệ từ 64 đến 800 byte ZIP mỗi phần, mặc định 512 byte. |
| `--parts-only` | Chỉ xuất `parts/` và `source-tree.txt` khi lưới QR quá lớn. |
| `--exclude '.env'` | Bỏ qua đường dẫn khớp mẫu glob tương đối với nguồn. Có thể lặp tùy chọn cho nhiều mẫu. |
| `--include-all` | Tắt bộ lọc mặc định cho các thư mục như `.git`, `.venv` và `node_modules`. |

Tệp ẩn được đóng gói theo mặc định. Dùng `--exclude` nếu nguồn chứa `.env`, khóa riêng hoặc các tệp khác cần loại khỏi bộ ảnh.

## Tài liệu và giấy phép

- Kiến trúc, cây mã nguồn và lịch sử phát triển nằm trong [project.md](project.md).
- Dự án dùng giấy phép [Apache 2.0](LICENSE).
