# Kiểm thử và kết quả

## Các lớp kiểm thử

| Nhóm | Nội dung | Cách chạy |
|---|---|---|
| Unit | Clock ban đầu/local/send/receive; cặp ưu tiên, ba trạng thái; deferred, request ID, duplicate/stale, schema, membership | `python -X utf8 -m pytest tests/unit -q` |
| Integration | 3/5 OS process thật, TCP thật, single/concurrent/all competing, release thủ công, framing chia gói, thiếu peer, restart phiên | `python -X utf8 -m pytest tests/integration -q` |
| API | FastAPI lifecycle local, validation, release sai state, WebSocket thật qua TestClient, reset session và cleanup | Cùng nhóm integration |
| Observer | Tắt và tạo lại monitor external trong khi node tiếp tục request/release | Cùng nhóm integration |
| Equal timestamps | Proxy TCP giữ REQUEST tới khi năm node tạo xong timestamp 1, rồi mở barrier; assert thứ tự P1…P5 | Cùng nhóm integration |
| Stress | 12 vòng × 5 node, kiểm tra đủ 60 lượt, 240 REQUEST + 240 REPLY và tiến triển | `python -X utf8 -m pytest tests/stress -q` |
| Giao diện thủ công | Các nút, timeline, mode, counters, responsive, Console và WS | [manual-testing.md](manual-testing.md) |

Chạy toàn bộ: `python -X utf8 -m pytest -q`. Không cần bật demo trước. Các test tự tạo cấu hình và cấp cổng tạm; bài API dùng runtime riêng của backend nhưng không dùng cổng mặc định 5001–5005. Không chạy test API lifecycle đồng thời một phiên demo local khác trong cùng workspace vì cùng thư mục `.runtime`.

## Kiểm tra safety độc lập

Mỗi node ghi audit JSONL vào file riêng. Bộ test thu thập các CS_ENTER/EXIT, sắp bằng bộ đếm hiệu năng độ phân giải cao `time.perf_counter_ns()` trên **cùng máy**, duy trì tập owner và assert:

```text
Trước mọi CS_ENTER: không có owner nào còn trong CS.
Tại CS_EXIT: đúng node đang là owner.
Kết thúc các lượt: không còn owner.
Số lượt entry đúng bằng số yêu cầu mong đợi.
```

Với từng entry, đối chiếu REPLY đã nhận trước đó theo `seq` trong journal chính node đó: phải đủ set N − 1 sender và đúng request ID. Đồng thời kiểm tra counters theo 2(N − 1), số lượt hoàn tất mỗi node và eventual progress bằng bounded condition polling. Không chỉ kiểm tra `max_owners <= 1` và không dựa vào frontend.

State machine không biết bộ kiểm tra audit; không có central lock trong test để vô tình làm an toàn thay cho protocol.

## Thời gian và đồng bộ

- Poll điều kiện với deadline, không sleep cố định rồi hy vọng xong.
- Readiness tối đa 45 giây: trên máy Windows này một interpreter đã bị trì hoãn khởi động hơn 15 giây; không phải deadline cấp quyền.
- Chờ tiến triển thường tối đa 12 giây. CS tự động 0.05–0.1 giây trong test để tránh HELD thủ công chặn test.
- Test peer lỗi cố ý chờ sự kiện cảnh báo sau tám giây và xác nhận vẫn WANTED.
- Equal timestamp dùng barrier truyền tin, không giả định các lệnh mạng đến cùng lúc.
- Cổng tạm được đặt trước khi launch, sau đó giải phóng cho node bind. Môi trường quá tải hoặc process khác tranh đúng cổng vẫn có thể làm fail; xem log trong thư mục pytest tạm để điều tra.
- Bộ đếm `time.monotonic_ns()` của Python 3.11/Windows có thể quá thô cho các sự kiện sát nhau. Audit dùng `perf_counter_ns`; quan hệ thứ tự trong cùng node dùng `seq`, không suy diễn từ wall clock.

## Môi trường thực thi bàn giao

Windows, Python 3.11, Node.js 22.20.0. Các thư viện Python sẵn có đã dùng: FastAPI 0.115.0, Pydantic 2.13.5, Uvicorn 0.30.6, pytest 8.3.2, pytest-asyncio 0.24.0, httpx 0.28.1. Frontend npm lockfile được lưu trong repository; build dùng Vite 6.4.6.

Kết quả thực thi và phạm vi kiểm chứng được ghi ở [test-results.md](test-results.md). Đợt sửa LAN 15/11/2026: 45 unit/integration tests đạt, frontend build đạt; HTTP/WebSocket xác nhận 3/4 node trên LAN, P3 chưa phản hồi cổng 5003.

## Phạm vi chưa kiểm chứng

- Không cài/chạy Playwright theo yêu cầu người dùng; giao diện có checklist tự test. Build TypeScript/Vite không thay thế kiểm tra bằng trình duyệt.
- Đã kiểm tra monitoring qua LAN với P1/P2/P4. Chưa xác nhận một phiên CS khỏe mạnh trên đủ bốn máy; Linux chưa chạy kiểm chứng.
- Không kiểm thử phục hồi lỗi, membership động hoặc mạng Byzantine vì không triển khai các khả năng này.

## Khi có test lỗi

Giữ nguyên assertion safety và permission, đọc traceback, cấu hình, stdout process và audit trong thư mục pytest tạm. Không xóa bài hoặc coi timeout là thành công. Với lỗi interpreter startup, phân biệt thời gian readiness và thời gian tiến triển của protocol.
