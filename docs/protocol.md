# Giao thức TCP và API

## Framing và truyền tải

UTF-8 JSON, mỗi frame kết thúc bằng byte `\n` (NDJSON). Mỗi connection phục vụ một request/response rồi đóng. Dùng `StreamReader.readline`, không giả định một lần đọc TCP tương đương một frame. Giới hạn reader 256 KiB, chờ request frame bốn giây; client RPC timeout hai giây gồm kết nối, gửi và nhận ACK.

Các schema Pydantic không chấp nhận trường lạ. Sai JSON, sai session/receiver/sender hoặc request timestamp không hợp lệ trả `{"ok":false,"error":"..."}`. Kết nối bị ngắt không được coi là quyền.

## Thông điệp thuật toán

```json
{"type":"REQUEST","session_id":"demo-1","sender_id":1,"receiver_id":2,"timestamp":8,"request_id":"unique-id","request_timestamp":7}
```

```json
{"type":"REPLY","session_id":"demo-1","sender_id":2,"receiver_id":1,"timestamp":12,"request_id":"unique-id"}
```

`timestamp` là clock gửi thông điệp, `request_timestamp` là clock bất biến lúc tạo yêu cầu. REQUEST yêu cầu `1 <= request_timestamp < timestamp`; REPLY không mang request_timestamp. ID thành viên là số nguyên dương duy nhất. Các node nhận cùng cấu hình bất biến trong mỗi phiên.

`{"ok":true}` trên connection chỉ là ACK ứng dụng rằng peer đã xử lý frame, **không phải REPLY**. REPLY protocol luôn được gửi thành một connection riêng từ node cấp quyền đến node yêu cầu. Không tính ACK này vào 2(N − 1).

Không tự retry khi ACK mất hoặc kết nối lỗi: hệ chờ quyền thiếu, ghi NETWORK_ERROR. Điều này bảo toàn an toàn, có thể mất tiến triển khi truyền thông không tin cậy. REQUEST trùng trong bộ nhớ gần đây được bỏ qua; REPLY trùng hoặc cũ không tăng set quyền. Giả định thuật toán vẫn là truyền tin tin cậy trong phiên khỏe mạnh.

## Management (tách khỏi protocol)

```json
{"type":"COMMAND","action":"REQUEST_CS","session_id":"demo-1","duration":3.0}
```

Action: `STATUS`, `REQUEST_CS`, `RELEASE_CS`, `SHUTDOWN`. `duration:null` giữ thủ công; số từ 0.05 đến 120 giây tự release. STATUS nhận `after` là seq cursor; trả tối đa 200 journal records cùng snapshot, PID, boot ID và lỗi mạng. `monitoring_backend` trong cấu hình mô tả địa chỉ observer cho vận hành; node không phụ thuộc URL này vì backend chủ động pull STATUS.

## HTTP API

| Method | Đường dẫn | Nội dung |
|---|---|---|
| GET | /api/health | Sức khỏe backend, không đại diện sức khỏe toàn bộ node |
| GET | /api/nodes | Snapshot các node có online/PID/clock/permissions |
| GET | /api/simulation/status | Membership, counters, owner quan sát, trạng thái |
| GET | /api/simulation/events?after=0&limit=200 | Journal theo collection_id; limit 1–1000 |
| POST | /api/simulation/start | Start local hoặc attach external |
| POST | /api/simulation/stop | Chỉ dừng node local được quản lý |
| POST | /api/simulation/reset | Phiên mới local; external từ chối |
| POST | /api/nodes/{id}/request | Body `{"duration":3}` hoặc `{"duration":null}` |
| POST | /api/nodes/{id}/release | Release nếu HELD |
| WS | /ws/events | Snapshot + delta sự kiện mỗi khoảng 200 ms |

HTTP 409: state/lifecycle không hợp lệ. HTTP 422: schema hoặc tham số không hợp lệ. HTTP 503: peer unreachable/timeout. Xem Swagger tại `/docs`.

## Sự kiện và bộ đếm

Sự kiện có `event_id = boot_id:seq`, node ID, clock, request ID, mô tả tiếng Việt, `observed_at` UTC tại node, `monotonic_ns` từ bộ đếm hiệu năng local. Khi thu thập backend thêm `collection_id` và `collected_at`. Không so sánh mốc bộ đếm hiệu năng giữa các máy khác nhau.

MESSAGE_SENT biểu diễn sự kiện gửi logic khi node tạo thông điệp và đưa vào outbox; không khẳng định peer đã nhận. MESSAGE_RECEIVED ở peer mới xác nhận frame đã được nhận/xử lý. Counter REQUEST/REPLY là số lần gửi logic, gồm lần có thể thất bại; ở mạng khỏe mạnh khớp số thông điệp thực và công thức 2(N − 1). Nếu lỗi, đối chiếu NETWORK_ERROR và MESSAGE_RECEIVED.

CS_ENTER/EXIT là sự kiện của node, không phải backend cấp quyền. Thứ tự collection không phải thứ tự nhân quả toàn cục. Trường request ID đầy đủ có trong JSONL/API, UI rút gọn cho dễ đọc.
