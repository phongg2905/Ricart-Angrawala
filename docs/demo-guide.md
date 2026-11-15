# Kịch bản thuyết trình cho năm thành viên

Thời lượng gợi ý 10–15 phút, demo local đã build, toàn bộ máy chạy offline. Chuẩn bị `python scripts/start_demo.py`, trình duyệt ở http://127.0.0.1:8000 và terminal thứ hai. Các bước thao tác đầy đủ ở [manual-testing.md](manual-testing.md).

## Thành viên 1 — Giới thiệu và lý thuyết (2 phút)

Nêu bài toán: nhiều tiến trình truy cập cùng resource phải tránh xung đột. Giới thiệu Ricart & Agrawala, ba trạng thái và hai thông điệp. Mở phần Thuật toán trong dashboard; chỉ ra `(T, ID)` và quy tắc N − 1 quyền. Nói rõ không có central lock coordinator, không dùng thời gian thực để chọn người thắng.

Chuyển tiếp: “Để các quyết định thực sự phân tán, mỗi node chạy trong một process riêng và trao đổi TCP.”

## Thành viên 2 — Mạng và kiến trúc (2 phút)

Mở `/api/nodes` cho thấy năm PID khác nhau, cổng 5001–5005. Trình bày `core/algorithm.py` không phụ thuộc backend; `node.py` sở hữu clock, state và listener. JSON có framing newline; ACK ứng dụng không phải quyền REPLY.

Mở sơ đồ Mermaid trong architecture.md. Backend chỉ gửi COMMAND và pull journal qua STATUS; WebSocket đưa sự kiện lên frontend. Giải thích config host/bind_host, fixed membership và chế độ external LAN.

## Thành viên 3 — Cài đặt thuật toán (3 phút)

Reset, chọn thủ công, P1 yêu cầu và chờ HELD. P2 yêu cầu: chỉ ra P2 WANTED, thiếu REPLY từ P1, deferred tại P1. Giải phóng P1 để P2 nhận REPLY và vào HELD; sau đó release P2.

Chỉ ra trong mã: request timestamp bất biến, clock gửi vẫn tăng; `replies` là set ID; release flush deferred ngoài network I/O. Đối chiếu tổng 8 REQUEST + 8 REPLY cho hai lượt hoàn tất.

## Thành viên 4 — Dashboard và cạnh tranh (3 phút)

Reset, chọn tự động 3 giây, tất cả node. Gửi đồng thời, quan sát các cặp ưu tiên và lần lượt HELD. Sau khi xong: 20 REQUEST, 20 REPLY, năm lượt hoàn tất.

Giải thích màu, bảng Lamport, log filter và xuất JSONL. Clock không giảm trong phiên; không bắt buộc năm request có cùng timestamp vì mạng xử lý bất đồng bộ. Animation chỉ minh họa sự kiện đã quan sát, không phải timing thật.

## Thành viên 5 — Kiểm thử và kết luận kỹ thuật (2–3 phút)

Chạy `python -X utf8 -m pytest -q` hoặc trình bày kết quả thật trong testing.md và chạy lại nhóm unit tại chỗ. Nêu unit, integration real process, barrier equal timestamp, stress 60 lượt, audit kiểm tra owner và quyền trước entry.

Nếu đủ thời gian: reset rồi dừng đúng PID P5 bằng hướng dẫn manual-testing; cho P1 yêu cầu, quan sát WANTED và cảnh báo sau tám giây. Nhấn Reset sau demo lỗi. Nêu giới hạn: không fault tolerance, membership động hay consensus; LAN nhiều máy chưa kiểm chứng thực tế trong phiên bàn giao.

## Câu hỏi giảng viên

| Câu hỏi | Trả lời ngắn |
|---|---|
| Backend có cấp quyền không? | Không. Mỗi node chỉ vào HELD khi set REPLY bằng toàn bộ peer cho request ID đang chờ. |
| Vì sao dùng request ID? | Để REPLY trễ của lượt trước không cấp quyền cho lượt hiện tại. Set sender chống đếm trùng. |
| Timestamp gửi và timestamp yêu cầu khác nhau thế nào? | Timestamp yêu cầu cố định dùng xếp ưu tiên; clock gửi tăng mỗi thông điệp để thể hiện nhân quả. |
| Hai yêu cầu cùng timestamp? | So ID; ID nhỏ hơn ưu tiên trước. Test TCP có barrier kiểm chứng trường hợp bằng nhau. |
| Vì sao HELD luôn hoãn? | Cấp quyền khi đang sử dụng CS có thể cho node khác vào chồng lấn. |
| Nếu node chết? | Các yêu cầu cần quyền của node đó có thể chờ mãi. Timeout chỉ cảnh báo, không cấp quyền. |
| Vì sao không bỏ qua node chết? | Việc đó thay membership và giả định protocol; cần thiết kế phục hồi khác. |
| Có đảm bảo không starvation? | Khi mạng tin cậy, membership cố định, mọi peer hoạt động và mỗi lượt HELD kết thúc, các yêu cầu tiến triển theo ưu tiên. |
| Một lượt tốn bao nhiêu message? | 2(N − 1); N=5 là tám, không tính STATUS, WebSocket, command và ACK. |
| Làm sao chứng minh an toàn? | Lập luận quyền hoãn của cặp ưu tiên và test audit riêng từng process; test là bằng chứng thực nghiệm, không thay chứng minh toán học. |
| Tại sao UI có thể thấy hai HELD thoáng qua? | Snapshot lấy khác thời điểm; trạng thái cũ chưa cập nhật. Đối chiếu audit trên cùng máy, không kết luận từ collection order. |
| Lamport có đồng bộ đồng hồ thật không? | Không; đây là thời gian logic. L(a) < L(b) không tự chứng minh a gây ra b. |
| Có chạy LAN không? | Có cấu hình, bind/advertised host và external node mode; cần kiểm chứng trên các máy và firewall cụ thể. |
| Resource dùng để demo là gì? | Vùng tới hạn logic trong mỗi node, ghi CS_ENTER/EXIT; audit/visualizer không cấp khóa. |
