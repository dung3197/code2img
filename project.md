# Code2Img

## Project dùng để làm gì

Code2Img nhận đường dẫn đến một tệp hoặc thư mục mã nguồn. Công cụ tạo QR theo từng tệp, xuất một ảnh tổng hợp để copy hoặc chụp và sinh `source-tree.txt` để tra cứu tệp cùng các QR tương ứng. Thiết bị nhận khôi phục cấu trúc thư mục và từng byte của tệp, gồm thụt lề, kiểu xuống dòng, encoding và tệp nhị phân.

## Quyết định trong kiến trúc

- `pack` nén riêng từng tệp bằng Deflate trong ZIP và bắt đầu một phần QR mới tại mỗi mục ZIP. Tệp lớn chiếm nhiều phần. Phần chỉ mục ZIP nằm cuối bộ ảnh. Thư mục rỗng được lưu thành mục ZIP riêng.
- Mỗi phần có mã định danh `C2I\x01`, SHA-256 của ZIP, số thứ tự và tổng số phần, rồi đến dữ liệu ZIP. Mỗi QR dùng mức sửa lỗi Q. Ảnh riêng trong `parts/` chứa tối đa 512 byte ZIP theo mặc định, có thể tăng lên 800 byte. Giới hạn bộ truyền là 65.535 phần.
- `project.png` chứa một QR chuẩn khi ZIP có tối đa 1.600 byte. Với dữ liệu lớn hơn, ảnh tổng hợp xếp các QR riêng thành một lưới có đường kẻ màu xanh để định vị các ô trong ảnh chụp. Một QR chuẩn có giới hạn dung lượng theo phiên bản và mức sửa lỗi. [DENSO WAVE](https://www.qrcode.com/en/about/version.html)
- `source-tree.txt` liệt kê cây đã đóng gói cùng số QR của từng tệp, thư mục rỗng và chỉ mục ZIP. Ảnh tổng hợp tự chứa dữ liệu khôi phục. Tệp cây nguồn dùng để tra cứu và có mã số tương ứng với bộ ảnh trong `parts/`.
- `unpack` và `serve` đọc ảnh tổng hợp hoặc các ảnh riêng theo thứ tự bất kỳ, bỏ qua phần lặp và báo số còn thiếu. Hai lệnh đọc được ảnh tạo từ 0.1.0. CLI kiểm tra SHA-256 và đường dẫn ZIP rồi giải nén vào thư mục mới. `serve` nhận ảnh dán, ảnh chụp hoặc tệp ảnh và trả `code2img.zip` qua localhost hoặc mạng nội bộ.
- Mặc định đóng gói tệp ẩn và bỏ qua `.git`, `.hg`, `.svn`, `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache` và `.ruff_cache`. `--include-all` tắt bộ lọc thư mục mặc định. Liên kết tượng trưng và tệp đặc biệt bên trong thư mục được bỏ qua. Dùng `--exclude` để bỏ các tệp không muốn chuyển, ví dụ `.env` hoặc khóa riêng.

## Ngôn ngữ sử dụng

- Python 3.10 trở lên cho CLI, nén ZIP và máy chủ HTTP cục bộ.
- Pillow và ZXing-C++ để tạo QR, ghép lưới và xuất ảnh PNG, JPEG hoặc WebP. Pillow và pillow-heif đọc ảnh từ điện thoại, gồm JPEG và HEIC/HEIF. ZXing-C++ được cố định ở bản 3.0.0 để dùng wheel dựng sẵn trên Python 3.10.
- HTML, CSS và JavaScript thuần cho trang nhận ảnh.

## Source code tree

```text
.
├── .gitignore
├── AGENTS.md                # Quy ước cập nhật project.md khi phát triển tính năng
├── LICENSE                  # Giấy phép Apache 2.0
├── README.md                # Hướng dẫn cài đặt, tạo ảnh và khôi phục mã nguồn
├── project.md               # Kiến trúc, lệnh sử dụng và lịch sử thay đổi
├── pyproject.toml           # Đóng gói, thư viện và lệnh code2img
└── code2img/
    ├── __init__.py
    ├── __main__.py          # CLI pack, unpack, serve
    ├── archive.py           # Lưu vị trí từng mục ZIP, kiểm tra và giải nén
    ├── transfer.py          # Chia QR theo mục ZIP, ghép phần và kiểm tra SHA-256
    ├── qr.py                # Tạo ảnh riêng, ghép lưới và đọc QR
    ├── source_tree.py       # Sinh cây nguồn và số QR tương ứng
    ├── receiver.py          # Máy chủ nhận ảnh và trả ZIP
    └── receiver.html        # Giao diện dán, chụp và chọn ảnh
```

## Function / command hay dùng

### Cài đặt

Chạy trong thư mục Code2Img trên máy tạo ảnh và máy chạy chức năng nhận.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

Trên Windows PowerShell, dùng `py -3 -m venv .venv` rồi chạy `.\.venv\Scripts\python.exe -m pip install .`. Dùng `.\.venv\Scripts\code2img.exe` thay cho `.venv/bin/code2img` trong các ví dụ.

### Tạo ảnh và khôi phục bằng lệnh

```bash
.venv/bin/code2img pack /duong/dan/ma-nguon -o ./qr-output
.venv/bin/code2img unpack ./qr-output/project.png -o ./ma-nguon-khoi-phuc
```

Thư mục đầu ra cần là đường dẫn chưa tồn tại. `pack` cũng nhận đường dẫn đến một tệp nguồn. Đầu ra mặc định gồm `project.png`, `source-tree.txt` và thư mục `parts/`. Chọn `--format jpeg` hoặc `--format webp` để đổi định dạng ảnh tổng hợp và ảnh riêng. Đặt thư mục ảnh bên ngoài nguồn nếu sẽ nén lại cùng nguồn.

`--exclude` nhận glob tính từ thư mục nguồn và có thể lặp lại. Giảm `--part-size` để từng QR thưa hơn. Số lượng QR của tệp lớn có thể tăng.

```bash
.venv/bin/code2img pack /duong/dan/ma-nguon -o ./qr-webp \
  --format webp --part-size 512 --exclude '.env'
.venv/bin/code2img unpack ./qr-webp/parts -o ./ma-nguon-tu-anh-rieng
```

`unpack` cũng nhận nhiều đường dẫn ảnh riêng. Với project vượt giới hạn kích thước lưới, dùng `pack --parts-only` để tạo `parts/` và `source-tree.txt`.

### Chụp hoặc dán ảnh và tải ZIP

1. Trên máy phát, mở `project.png` để copy hoặc chụp toàn bộ ảnh. Nếu ảnh chứa lưới, giữ đủ các cạnh màu xanh trong khung hình. Dùng ảnh gốc nếu bản chụp làm các ô QR quá nhỏ hoặc mờ.
2. Trên máy nhận, chạy `.venv/bin/code2img serve` rồi mở `http://127.0.0.1:8765`. Nếu muốn mở trang trên điện thoại, chạy `.venv/bin/code2img serve --host 0.0.0.0` và dùng `http://<IP-máy-nhận>:8765` trên điện thoại cùng mạng nội bộ.
3. Dán ảnh vào trang hoặc bấm **Chụp ảnh** hay **Chọn ảnh**. Nếu thiếu phần từ ảnh lưới, thêm ảnh QR riêng tương ứng trong `parts/`.
4. Khi nhận đủ các phần, bấm **Tải ZIP** và giải nén trên thiết bị đích.

Các hàm chính gồm `write_zip()` và `extract_zip()` cho ZIP, `split_zip()` và `Transfer.assemble()` cho dữ liệu truyền, `grid_image()` và `read_qrs()` cho ảnh, cùng `write_source_tree()` cho tệp cây nguồn.

## Lịch sử phát triển

- **2026-11-26 · 0.1.0** — Khởi tạo project. Thêm lệnh `pack`, `unpack` và `serve`, giao diện nhận ảnh trên trình duyệt, kiểm tra tính toàn vẹn và quy ước cập nhật tài liệu qua `AGENTS.md`.
- **2026-11-26 · 0.2.0** — Chia QR theo từng tệp, ghép ảnh tổng hợp, thêm lựa chọn PNG/JPEG/WebP, hỗ trợ nén một tệp và sinh `source-tree.txt`.
- **2026-11-26** — Bổ sung hướng dẫn cài đặt trên Linux, macOS và Windows, tạo ảnh QR và khôi phục mã nguồn trong `README.md`.
