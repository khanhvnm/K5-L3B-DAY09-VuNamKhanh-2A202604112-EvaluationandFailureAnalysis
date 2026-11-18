# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline v1 `E-swarm-20261118-1454` / `1454c42d435d`; baseline v2 `E-swarm-20261118-fc3f` / `fc3fbf6167ef`
- **Phiên bản:** nhánh `starter/d09`; metric_spec v1 `1.0`, v2 `2.0`; grader commit sau M3; seeds 11/22/33/44/55
- **Eval set:** v1 14 item × 5 seed, nguồn lab8_public; v2 28 item × 5 seed, gồm 14 public và 14 adversarial; nhãn tách riêng
- **Metric & ngưỡng:** xem `src/config/metric_spec.yaml` và `src/config/metric_spec_v2.yaml`
- **Kết quả baseline vs PR:** v1 swarm pass_rate 0.9857; fixed pass_rate 1.0 exit 0; seeded_regression pass_rate 0.7143, Δ -0.271, CI [-0.500, -0.057] exit 1
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800 đạt floors; helpful κ=0.375, P=1.000, R=0.300 bị loại
- **Trace case:** [docs/trace_case.md](trace_case.md): FM-03, event `model_override` là bước sai đầu tiên ở C-002@55
- **Gate owner:** Eval owner chịu trách nhiệm xử lý exit 1; waiver chỉ được duyệt trong PR kèm lý do
- **Phạm vi pilot:** MockLLM offline, 14 claim public ở v1 và 28 claim ở v2, không chạy trên người dùng thật
- **Giới hạn / bằng chứng còn thiếu:** chỉ kiểm tra 5 seed, 14 item mẫu v1 nhỏ nên CI rộng; judge replay mới công khai, chưa có held-out người thật
- **Khi nào tăng eval-set version:** khi thay eval set bằng item/tình huống mới hoặc mở adversarial pack; chạy lại baseline và metric spec với cùng quy trình
- **M6 A/A:** seed thay thế 66/77/88/99/110 cho Δ=0 trên mọi metric; bug 1/5 seed bị chặn bởi `pass_hat_5=0.5714 < 0.80`
