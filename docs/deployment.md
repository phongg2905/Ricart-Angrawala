# Chạy cục bộ và LAN

## Cục bộ

Làm theo README để cài và build, chạy `python scripts/start_demo.py`. Backend phục vụ frontend tại cổng 8000, spawn các node trên 5001–5005. Không cần một Vite server khi dùng bản build.

Cấu hình qua biến môi trường (không tự đọc file `.env`; `.env.example` là mẫu):

```powershell
$env:RA_CONFIG = 'config/nodes.example.json'
$env:RA_HOST = '127.0.0.1'
$env:RA_PORT = '8000'
python scripts/start_demo.py
```

Không chạy đồng thời hai launcher trên cùng membership/cổng. Khi lỗi cổng đang dùng, kiểm tra trước khi tự dừng đúng PID:

```powershell
Get-NetTCPConnection -LocalPort 5001,5002,5003,5004,5005,8000 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
```

Backend từ chối chiếm cổng đã có process; không tự kill tiến trình không sở hữu. Dùng Ctrl+C tại terminal cũ, hoặc nút Dừng / `scripts/stop_demo.py` nếu monitor còn hoạt động. Sau crash hãy kiểm tra PID và session trong `.runtime/session.json` rồi kết thúc toàn phiên trước khi chạy phiên mới.

## LAN năm máy

Ví dụ dùng dải `192.168.1.101` … `.105` trong `config/nodes.lan.example.json`. Thay IP bằng IPv4 thực tế lấy từ `ipconfig`. Cố định IP hoặc DHCP reservation trong suốt phiên. Cả năm máy dùng cùng file và cùng session_id.

| Máy | Node | IP quảng bá | TCP |
|---|---|---|---|
| 1 | P1 + dashboard | 192.168.1.101 | 5001 và HTTP 8000 |
| 2 | P2 | 192.168.1.102 | 5002 |
| 3 | P3 | 192.168.1.103 | 5003 |
| 4 | P4 | 192.168.1.104 | 5004 |
| 5 | P5 | 192.168.1.105 | 5005 |

`host`: địa chỉ peer/monitor có thể truy cập. `bind_host`: địa chỉ interface trên chính máy node; `0.0.0.0` lắng nghe các interface. `port`: cổng của node. Mỗi ID là duy nhất. `mode:external` đánh dấu lifecycle của node do các terminal/máy riêng quản lý. `monitoring_backend` ghi địa chỉ dashboard, không ảnh hưởng quyền CS.

1. Cài dependency Python trên năm máy; build frontend trên máy dashboard.
2. Sửa config, phân phối cùng config. Thay session_id trước mỗi phiên mới sau khi dừng **tất cả** node phiên cũ.
3. Trên máy i, chạy `python scripts/start_node.py --id i --config config/nodes.lan.example.json`. Không chạy hai node cùng ID.
4. Cho phép Python hoặc cổng node inbound trên Windows Firewall ở profile Private; chỉ trong LAN thực hành. Dashboard cần kết nối được đến tất cả node, mọi node cũng phải kết nối được đến tất cả peer.
5. Trên máy 1:

```powershell
$env:RA_CONFIG = 'config/nodes.lan.example.json'
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

6. Mở `http://192.168.1.101:8000`. Không gửi yêu cầu đến khi thấy đủ 5/5.
7. Khi kết thúc, Ctrl+C từng node và dashboard. Nút Dừng/Reset bị vô hiệu ở external; dashboard không giả vờ điều khiển lifecycle máy từ xa.

## Kiểm tra truy cập

```powershell
Test-NetConnection 192.168.1.102 -Port 5002
```

Thử từ dashboard **và từ các máy peer**, không chỉ trên máy đích. Ping hoạt động không đảm bảo TCP port mở. Kiểm tra subnet, Wi-Fi client isolation, VPN, firewall profile, bind host và IP thay đổi.

## Monitor disconnect / restart

Node không cần monitor để xử lý REQUEST/REPLY hoặc tự release. Trong external mode, có thể đóng dashboard và mở lại với **cùng config/session** để đọc tiếp trạng thái. Journal node có giới hạn, nên restart monitor quá lâu có thể thiếu lịch sử; có sự kiện OBSERVATION_GAP. Không tự restart node lỗi vào giữa phiên.

Chế độ local: thoát sạch backend dừng các child theo thiết kế. Nếu cần quan sát các node độc lập qua nhiều lần restart monitor, chạy node thủ công và dùng `external`.

## Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python scripts/start_demo.py
```

Mã dùng pathlib và asyncio, không yêu cầu Windows API cho thuật toán. Bản này đã thực thi trên Windows; tương thích Linux theo thiết kế, chưa chạy xác nhận trên Linux trong phiên bàn giao.

**LAN vật lý nhiều máy chưa được kiểm chứng trong môi trường bàn giao này.** Các bài integration dùng nhiều OS process và TCP loopback thật trên một máy.
