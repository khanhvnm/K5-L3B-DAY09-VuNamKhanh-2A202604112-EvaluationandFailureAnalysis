# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không | loại khỏi gate |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | "Em ... nha" không phù hợp giọng thưa khách; sửa rubric: chấm FAIL khi xưng hô suồng sã hoặc dùng "em/nha". |
| 2 | H-017 | PASS | FAIL | Người đúng | "bạn ơi ... nha" không phù hợp ngữ cảnh khách lớn tuổi; thêm từ/cặp xưng hô bị cấm. |
| 3 | H-029 | PASS | FAIL | Người đúng | Câu có vẻ lễ phép ở đầu nhưng có giọng ra lệnh "không cần nhắn thêm"; rubric phải chấm tổng thể câu, không chỉ từ mở đầu. |
| 4 | H-042 | FAIL | PASS | Người đúng | Câu ngắn nhưng nêu đúng trạng thái, số tiền và thời gian; rubric không được yêu cầu bắt buộc mẫu hoặc từ "xin lỗi". |
| 5 | H-051 | FAIL | PASS | Người đúng | "refund" là từ người dùng cho phép trong ngữ cảnh LogiX; bỏ quy tắc bắt buộc toàn bộ câu dùng tiếng Việt thuần. |
| 6 | H-063 | PASS | FAIL | Người đúng | Hứa "hoàn thêm" ngoài kết quả hệ thống; rubric thêm lỗi hứa cam kết không có trong ledger. |
| 7 | H-070 | PASS | FAIL | Người đúng | Emoji không phù hợp ngữ cảnh khiếu nại; rubric thêm cấm emoji và ký hiệu trò chuyện không trang trọng. |
| 8 | H-081 | FAIL | PASS | Judge đúng | Mẫu nhãn sai trong CSV ghi PASS dù judge nói câu chính sách chưa đủ điều kiện; sửa nhãn thành FAIL. |
| 9 | H-088 | FAIL | PASS | Người đúng | Lặp "Dạ, dạ" là lỗi gõ nhỏ, không khiến câu thiếu ý hoặc sai tiền; rubric không phạt lỗi đánh máy nhỏ. |
| 10 | H-094 | PASS | FAIL | Người đúng | Câu dịch máy, thiếu dấu; rubric thêm kiểm tra khả năng đọc và ngôn ngữ đúng cho hotline. |

## Kết luận
- `tone_ok` đạt FLOORS (κ=0.757, P=0.857, R=0.800), nên có thể dùng sau calibration, nhưng không dùng làm grader tiền hoặc approval.
- `helpful` bị loại khỏi gate: κ=0.375 và recall=0.300 dù precision=1.000. Judge bỏ sót 21/30 thất bại theo nhãn người, thể hiện ma trận nhầm lẫn nghiêm trọng trong CM `tp=9, fp=0, fn=21, tn=70`.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật và kiểm tra drift rubric.
