# Thuật toán Ricart & Agrawala

## Mục tiêu và giả định

Cho N tiến trình cùng chia sẻ một vùng tới hạn (CS), cần bảo đảm nhiều nhất một tiến trình ở trong CS. Không có coordinator cấp khóa. Mỗi tiến trình biết cố định toàn bộ N thành viên, có ID duy nhất và trao đổi thông điệp tin cậy. Không giả định đồng bộ đồng hồ thực.

## Trạng thái

| Trạng thái | Ý nghĩa | Xử lý REQUEST của peer |
|---|---|---|
| RELEASED | Không yêu cầu CS | REPLY ngay |
| WANTED | Đã gửi yêu cầu, đang chờ quyền | So sánh cặp ưu tiên |
| HELD | Đã đủ quyền, đang trong CS | Hoãn REPLY |

Chu trình hợp lệ: RELEASED → WANTED → HELD → RELEASED. Gọi request khi WANTED/HELD hoặc release khi không HELD bị từ chối. Dừng phiên là thao tác quản lý, không phải một chuyển trạng thái cấp quyền.

## Đồng hồ Lamport

- Ban đầu C = 0.
- Tạo sự kiện local cần timestamp: C ← C + 1.
- Trước mỗi thông điệp protocol được tạo để gửi: C ← C + 1.
- Khi nhận thông điệp timestamp T: C ← max(C, T) + 1.

Tạo yêu cầu: tăng C, lưu `request_timestamp = C` và request ID mới; cặp ưu tiên `(request_timestamp, process_id)` **không đổi** trong cả lượt chờ/HELD. Khi broadcast, mỗi REQUEST có timestamp gửi riêng lớn hơn timestamp yêu cầu. Clock vẫn tăng khi nhận REPLY hoặc phục vụ peer; điều đó không làm đổi thứ tự ưu tiên của yêu cầu đang chờ.

Timestamp Lamport biểu diễn quan hệ nhân quả theo một chiều: nếu a xảy ra trước b theo happens-before thì L(a) < L(b). Chiều ngược lại không luôn đúng.

## Quy tắc xử lý

Pi muốn vào CS:

1. RELEASED → WANTED; tạo request ID duy nhất và cặp ưu tiên.
2. Gửi N − 1 REQUEST đến tất cả peer.
3. Thu thập REPLY đúng session, đúng receiver, đúng request ID và từ thành viên hợp lệ. Set sender ID bảo đảm không đếm trùng.
4. Chỉ khi set quyền bằng chính xác toàn bộ peer mới WANTED → HELD.

Pi nhận REQUEST của Pj:

- RELEASED: REPLY ngay.
- HELD: lưu REPLY cần gửi sau.
- WANTED: nếu `(Tj, j) < (Ti, i)` thì REPLY ngay; nếu yêu cầu của mình đứng trước thì hoãn.

Pi rời CS: tăng clock cho sự kiện local, HELD → RELEASED, tăng số lượt hoàn tất, ghi CS_EXIT; gửi hết REPLY hoãn, xóa hàng đợi và trạng thái yêu cầu cũ. Runtime đưa các thông điệp vào outbox rồi gửi bất đồng bộ; không giữ state lock qua network I/O.

## Ví dụ ba tiến trình

P1 và P2 cùng tạo yêu cầu tại clock 1: `(1,1)` và `(1,2)`. P3 đang RELEASED.

1. P3 gửi REPLY cho P1 và P2.
2. P2 nhận REQUEST P1, thấy `(1,1) < (1,2)` nên trả lời.
3. P1 nhận REQUEST P2, hoãn vì ưu tiên của mình trước.
4. P1 có REPLY từ P2, P3 và vào HELD. P2 thiếu quyền từ P1 nên vẫn WANTED.
5. P1 ra CS rồi gửi REPLY hoãn cho P2.
6. P2 đủ REPLY từ P1, P3 và vào HELD.

`tests/integration/test_processes.py` dùng proxy TCP có barrier để cả năm node tạo timestamp bằng 1 trước khi chuyển phát REQUEST. Kiểm thử sau đó yêu cầu thứ tự HELD P1, P2, P3, P4, P5; không dựa vào scheduler để hy vọng timestamp bằng nhau.

## Vì sao an toàn

Giả sử hai yêu cầu cạnh tranh cùng HELD. Chọn yêu cầu có cặp ưu tiên nhỏ hơn. Trong lúc yêu cầu đó WANTED/HELD, node sở hữu nó sẽ hoãn quyền cho yêu cầu có ưu tiên sau, nên yêu cầu sau không thể đã có đủ quyền. Nếu nó đã trả quyền trước khi tự tạo yêu cầu, Lamport của yêu cầu tạo sau sẽ phản ánh REQUEST đã nhận và có thứ tự tương ứng. Hai node không thể đồng thời có quyền đầy đủ cho hai yêu cầu xung đột dưới các giả định trên.

Ưu tiên nhỏ nhất là điều kiện dùng để quyết định hoãn/trả lời, không thay thế việc đợi N − 1 quyền. Không diễn giải thứ tự thu thập log thành thứ tự toàn cục cho các yêu cầu không liên quan.

## Tiến triển, công bằng và độ phức tạp

Khi mạng tin cậy, mọi peer hoạt động và mỗi lượt HELD kết thúc, yêu cầu có ưu tiên trước sẽ thu đủ quyền; khi ra sẽ chuyển quyền hoãn cho yêu cầu kế tiếp. Các yêu cầu về sau không liên tục vượt yêu cầu trước trong hệ ổn định.

Mỗi lượt hoàn tất cần N − 1 REQUEST + N − 1 REPLY = **2(N − 1)** thông điệp protocol, không tính management, ACK RPC và monitoring. N = 5: tám thông điệp. Với năm node cùng yêu cầu một lượt: 20 REQUEST + 20 REPLY.

## Lỗi

Peer crash, thông điệp không được chuyển phát hoặc HELD thủ công không release có thể chặn các yêu cầu khác. Runtime cảnh báo lỗi gửi và chờ quá tám giây; tuyệt đối không coi timeout là một REPLY. Retry, khôi phục, Byzantine, thay membership và consensus ngoài MVP. Muốn làm lại sau crash phải tạo phiên mới cho tất cả node.
