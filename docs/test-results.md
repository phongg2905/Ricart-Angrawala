# Kết quả kiểm chứng

## Ngày 15/11/2026 — sửa kết nối LAN 4 node

- `python -X utf8 -m pytest tests/unit tests/integration -q`: **45 passed in 31.86s**. Gồm 32 unit tests và 13 integration tests; có các kịch bản 4 process TCP thật, timeout rõ địa chỉ, sai membership, reconnect và API/WebSocket.
- `npm.cmd run build`: TypeScript và Vite build thành công; JS 266.60 kB, CSS 28.37 kB trước gzip.
- Backend khởi chạy bằng `scripts/start_dashboard.py --config config/nodes.lan.4nodes.json --port 8010`, in đúng session `lan-4nodes-001` và bốn địa chỉ.
- Đã xác nhận HTTP API và WebSocket thật cùng báo **3/4 node online**: P1 tại 192.168.1.204:5001, P2 tại 192.168.1.40:5002, P4 tại 192.168.1.153:5004. HTML và hai asset JS/CSS trả HTTP 200.
- P3 tại 192.168.1.199:5003 chưa phản hồi TCP trong lần đo này; chưa thể kết luận do node chưa chạy hay firewall. Không ghi nhận cả bốn node khỏe mạnh hoặc request CS qua LAN thành công.
- Đã sửa IP mẫu trong file 4 node và bổ sung tên file/session, địa chỉ cùng lỗi kết nối trên dashboard. Các node đã chạy trước khi sửa file cần được khởi động lại với cùng bản cấu hình để dùng đúng địa chỉ peer.

## Phạm vi

Nhóm stress 60 lượt đã đạt trong lần kiểm thử trước (14/11); không chạy lại trong đợt sửa quan sát/cấu hình này. Thuật toán và TCP protocol không thay đổi. Chưa xác minh giao diện bằng trình duyệt tự động theo lựa chọn của người dùng; frontend đã build và HTTP/assets/WebSocket đã kiểm tra. Linux và một phiên CS khỏe mạnh trên đủ bốn máy LAN chưa được xác nhận.

Hướng dẫn chạy: [lan-4nodes.md](lan-4nodes.md). Checklist trình duyệt: [manual-testing.md](manual-testing.md).
