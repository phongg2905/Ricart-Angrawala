# Phiên LAN 4 node

File `config/nodes.lan.4nodes.json` dùng bốn IP của phiên nhóm đã xác nhận:

| Node | Địa chỉ TCP |
|---|---|
| P1 | 192.168.1.204:5001 |
| P2 | 192.168.1.40:5002 |
| P3 | 192.168.1.199:5003 |
| P4 | 192.168.1.153:5004 |

IP có thể đổi khi đổi mạng / DHCP; kiểm tra lại bằng `ipconfig`. Cả nhóm phải dùng cùng một bản file. Sửa file trên đĩa không cập nhật cấu hình của các process đang chạy.

1. Dừng các node phiên trước bằng Ctrl+C trong từng terminal. Dừng backend cũ trên máy dashboard.
2. Phân phối file cấu hình mới cho cả bốn máy. Không chỉ sửa file trên máy dashboard: mỗi node cũng cần đúng địa chỉ các peer.
3. Mỗi máy chạy node với ID được phân công, ví dụ P1:

```powershell
python scripts/start_node.py --id 1 --config config/nodes.lan.4nodes.json
```

Máy P2/P3/P4 thay `--id` tương ứng. Giữ terminal mở.

4. Máy P1 mở terminal khác để chạy dashboard bằng file chỉ định trực tiếp:

```powershell
python scripts/start_dashboard.py --config config/nodes.lan.4nodes.json --port 8010
```

Lệnh in đường dẫn config, session ID, bốn node và địa chỉ trước khi mở server. Không cần đặt RA_CONFIG; lệnh này tự chọn đúng file và ghi đè giá trị biến môi trường cũ cho tiến trình dashboard.

5. Cả nhóm mở `http://192.168.1.204:8010`. Panel mạng phải hiện file `nodes.lan.4nodes.json`, session `lan-4nodes-002` và bốn node. Trước khi chuyển sang phiên mới này, dừng toàn bộ node/backend phiên cũ rồi cho cả nhóm dùng cùng bản file mới.

Nếu còn một node offline, đọc địa chỉ/lỗi ngay trên dashboard. Mở được trang web chỉ xác nhận cổng 8010, không chứng minh cổng node đã mở. Ví dụ P3 cần nghe `0.0.0.0:5003`; từ máy khác kiểm tra:

```powershell
Test-NetConnection 192.168.1.199 -Port 5003
```

Nếu False: kiểm tra terminal P3 vẫn chạy, IP đúng, Windows Firewall cho phép Python/cổng 5003 inbound trên mạng Private, Wi-Fi không cô lập thiết bị. Không tắt toàn bộ firewall.

Đợi 4/4 trước bài test khỏe mạnh. Một lượt thành công: 3 REQUEST + 3 REPLY; cả bốn node mỗi node một lượt: 12 REQUEST + 12 REPLY. Nếu peer lỗi, yêu cầu vẫn chờ quyền, không tự vào HELD.

Sau crash hoặc khởi động lại node trong phiên đã có yêu cầu, dừng cả bốn node, đổi cùng session_id mới và khởi động lại toàn phiên. Restart riêng dashboard external không làm mất state của node.
