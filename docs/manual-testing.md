# Checklist tự test bằng trình duyệt

Không cần cài Playwright hay công cụ tự động hóa trình duyệt. Chuẩn bị hai cửa sổ PowerShell và Chrome/Edge/Firefox.

## 1. Chạy ứng dụng

Nếu chưa cài dependency, làm phần Cài đặt trong README. Sau đó, tại thư mục gốc:

```powershell
python scripts/start_demo.py
```

Hoặc thay `python` bằng `.\.venv\Scripts\python.exe` nếu cài trong virtual environment. Mở **http://127.0.0.1:8000**. Dùng `Ctrl+Shift+R` nếu vừa build frontend mới.

Nếu cổng 8000 đã có ứng dụng khác, chạy `python scripts/start_demo.py --port 8010`, mở **http://127.0.0.1:8010** và đổi 8000 → 8010 trong các lệnh HTTP ở checklist. Với script kiểm tra, thêm `--url http://127.0.0.1:8010`. Không cần dừng ứng dụng đang chiếm 8000.

Kết quả mong đợi:

- Dashboard tiếng Việt, trạng thái **Đã kết nối**, **ĐANG CHẠY**, tiến trình **5/5**.
- P1–P5 đều RELEASED/Thả, clock = 0, chưa có chủ sở hữu.
- REQUEST = 0, REPLY = 0, hoàn tất = 0.
- Nhật ký có NODE START thật. Không được có log REQUEST/REPLY khi chưa gửi yêu cầu.
- Mở `http://127.0.0.1:8000/api/nodes`: năm node có **năm PID khác nhau**.

Lệnh terminal kiểm tra nhanh:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/nodes | Format-Table id,pid,state,clock,online
```

Hoặc kiểm tra HTTP, năm PID độc lập, file frontend và WebSocket thật bằng script chỉ đọc (không cài thêm công cụ và không tạo yêu cầu CS):

```powershell
python scripts/check_running_demo.py
```

## 2. Một yêu cầu tự động

1. Nhấn **Reset toàn bộ phiên** (biểu tượng mũi tên vòng) để bắt đầu từ 0.
2. Chọn **Tự động**, thời gian **3 giây**, chọn **P1**.
3. Nhấn **Yêu cầu vùng tới hạn** một lần.
4. Quan sát P1: WANTED/Muốn → HELD/Giữ → RELEASED/Thả.

Kết quả cuối: **REQUEST = 4**, **REPLY = 4**, **hoàn tất = 1**. Nhật ký có CS ENTER rồi CS EXIT của P1. REQUEST mang cùng request ID và request timestamp, nhưng timestamp gửi có thể khác nhau. Khi đủ quyền, P1 có 4/4 REPLY; sau release, quyền của lượt cũ được xóa.

WANTED có thể rất ngắn trên loopback và không kịp hiện thành một frame UI; kiểm tra REQUEST_CREATED và CS_ENTER trong timeline/JSONL. Animation không mô tả chính xác thời gian trên dây.

## 3. Hai node cạnh tranh, kiểm tra REPLY hoãn

1. Reset, chọn **Thủ công**, chọn P1 → yêu cầu.
2. Chờ P1 **HELD** (sẽ giữ tới khi tự giải phóng).
3. Chọn P2 → yêu cầu.
4. Chờ log **DEFERRED** ở P1.

Lúc này: P1 HELD, P2 WANTED; P1 hoãn quyền cho P2. P2 không thể đủ 4 REPLY khi P1 chưa release. Nút Request trên P2 bị vô hiệu vì P2 đã WANTED; nút Release P2 cũng bị vô hiệu vì chưa HELD.

5. Chọn P1 → **Giải phóng vùng tới hạn**.
6. P1 RELEASED, gửi REPLY đã hoãn, P2 chuyển HELD.
7. Chọn P2 → Giải phóng.

Kết quả cuối: **REQUEST = 8**, **REPLY = 8**, **hoàn tất = 2**. Nhật ký P1 CS EXIT phải có trước việc P2 CS ENTER theo quan hệ chuyển quyền (thứ tự collection trên UI có thể bị trễ giữa các node).

## 4. Gửi yêu cầu đồng thời P1/P2

1. Reset, chọn Tự động, 3 giây.
2. Chọn nhóm **P1 + P2**, nhấn **Gửi yêu cầu đồng thời**.
3. Đối chiếu bảng clock và cặp ưu tiên của hai yêu cầu đang cạnh tranh.

Kết quả cuối: REQUEST = 8, REPLY = 8, hoàn tất = 2. Hai lệnh được gửi gần đồng thời; **không bắt buộc** timestamp bằng nhau trên mạng thật. Nếu timestamp bằng nhau, ID nhỏ hơn có ưu tiên. Bài integration có barrier riêng để kiểm chứng trường hợp timestamp bằng nhau một cách xác định.

## 5. Năm node cạnh tranh

1. Reset, Tự động, 3 giây, nhóm **Tất cả node**.
2. Gửi yêu cầu đồng thời.
3. Chờ tất cả node trở về RELEASED.

Kết quả cuối: **REQUEST = 20**, **REPLY = 20**, **hoàn tất = 5**. Mỗi node hoàn tất một lượt. Không có quyền cấp tập trung; thử xem GET `/api/nodes` để đối chiếu từng node.

Snapshot lấy bất đồng bộ có thể nhất thời chứa HELD cũ và mới. Khi đó UI hiển thị đang đồng bộ/chờ xác nhận, không kết luận lỗi thuật toán chỉ từ một frame. Chạy pytest để kiểm tra các khoảng HELD bằng audit.

## 6. Peer mất kết nối: phải chờ quyền

Chỉ làm sau khi reset và không node nào đang HELD. Tại terminal thứ hai, lấy PID của P5:

```powershell
$demoNodes = Invoke-RestMethod http://127.0.0.1:8000/api/nodes
$peerToStop = $demoNodes | Where-Object { $_.id -eq 5 }
$peerToStop | Format-List id,pid,state,online
# Chỉ dừng PID vừa xác nhận là P5 của demo:
Stop-Process -Id $peerToStop.pid
```

Sau đó:

1. Dashboard báo 4/5, P5 offline và cảnh báo thiếu node.
2. Chọn P1 đang online/RELEASED → yêu cầu, chế độ tự động 3 giây.
3. P1 phải ở WANTED, không có REPLY từ P5, không vào HELD.
4. Nhật ký có NETWORK ERROR; sau khoảng 8 giây có WAIT WARNING.
5. Chờ quá 3 giây hoặc quá cảnh báo vẫn không được tự vào HELD. Thời gian tự release chỉ bắt đầu khi node thực sự HELD.
6. Nhấn Reset để dừng cả phiên và chạy lại năm node với session mới. Không tự khởi động lại riêng P5 vào phiên cũ.

## 7. Dừng, reset và đóng ứng dụng

- Nhấn **Dừng**: số node online trở về 0, request/release bị vô hiệu; dashboard vẫn truy cập được.
- Nhấn **Khởi động**: năm process mới, clock/counter từ 0.
- Reset khi đang WANTED/HELD thủ công: toàn bộ phiên cũ được dừng; phiên mới không giữ quyền cũ.
- Ctrl+C tại terminal launcher: web server kết thúc và năm child process được dọn.

Kiểm tra cổng sau khi thoát:

```powershell
Get-NetTCPConnection -LocalPort 5001,5002,5003,5004,5005,8000 -State Listen -ErrorAction SilentlyContinue
```

Không nên còn listener của demo. Nếu cổng có ứng dụng khác đang dùng, đối chiếu `OwningProcess`, không dừng nhầm PID.

## 8. Nhật ký và giao diện

- Bấm từng node trên đồ thị hoặc nút P1–P5: vùng điều khiển và hàng được chọn đổi theo.
- Lọc timeline REQUEST / REPLY / Vùng tới hạn, lọc theo node.
- Nút thùng rác chỉ xóa log đang hiển thị, không thay counters/clock/trạng thái node.
- Nút tải xuống xuất JSONL. Mỗi dòng phải là JSON hợp lệ với event ID, node ID, clock, request ID khi có.
- Mở phần Thuật toán và Hướng dẫn demo ở thanh bên; quay lại mô phỏng.
- Thu hẹp cửa sổ khoảng 390 px: các panel xếp dọc, bảng clock cuộn ngang, điều khiển dùng được.
- Dùng Tab / Enter để chọn điều khiển; kiểm tra focus nhìn thấy được.
- F12 → Console: không lỗi JavaScript. Network → WS `/ws/events`: có frame snapshot liên tục.
- Tắt mạng monitor hoặc đóng backend ở chế độ external: trạng thái kết nối đổi, UI không giả vờ dữ liệu vẫn realtime; node độc lập vẫn xử lý quyền.

## 9. Chạy bộ test để đối chiếu

```powershell
python -X utf8 -m pytest -q
```

Không cần mở trình duyệt hoặc chạy demo. Test tự cấp cổng tạm, tạo và dọn process. Một bài cố tình dừng peer rồi chờ cảnh báo tám giây; thời gian khởi động interpreter có thể tăng do antivirus.

Nếu gặp lỗi, lưu terminal pytest, `.runtime/node-*.log`, `.runtime/audit/node-*.jsonl`, JSONL tải từ UI và mô tả bước tái hiện. Không dùng animation hoặc ảnh chụp một snapshot để khẳng định vi phạm mutual exclusion.
