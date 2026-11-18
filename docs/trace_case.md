# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@55`, run ID `E-seeded_regression-20261118-1454` |
| Triệu chứng | Lab 8 grader fail (`status resolved != denied`) và ledger ghi refund 20.000đ trong khi nhãn yêu cầu 0đ |
| Bước sai đầu tiên | Event 3, kind `model_override`, payload `{"delay_days": 5}`: ghi đè `delay_days=2` trong DB bằng ticket |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` và event 2 `investigator` đã giữ dữ liệu DB hợp lệ; chỉ event 3 mới thay đổi độ trễ trước quote |
| Failure mode | FM-03 `ticket_trust — tin ticket hơn DB` |
| Đối chứng | `fixed C-002@55` không có `model_override`; quote là 0đ, ledger 0đ, status `denied`, Lab 8 grader PASS |
| Regression test | `test_override_event_breaks_db_fact` kiểm tra `DbFactKept`; seeded/regression tạo event sai còn fixed không tạo event |
| Chưa chắc chắn | Trace không chứng minh nguyên nhân ticket được parse sai ở mọi seed; nhưng seed 55 tái hiện rõ lỗi ghi đè DB |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
