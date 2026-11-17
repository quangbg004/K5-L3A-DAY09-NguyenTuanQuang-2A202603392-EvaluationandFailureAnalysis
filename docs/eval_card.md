# Eval card — LogiX-VN refund agent

- Eval set **v1**, SHA **`4d60de93eb7a`**, metric spec **1.1**. 14 public claim từ Lab 8 × 5 seed `11, 22, 33, 44, 55`. Nhãn riêng ở `src/data/eval/labels_v1.json`.
- Runner `lab9.eval` dùng MockLLM và Python 3.12.6 cho các report bên dưới. Mỗi lượt dùng SQLite mới. Code và grader đi cùng bài nộp.
- Baseline `E-swarm-20261117-4d60`. Đối chứng `E-fixed-20261117-4d60`. Biến thể lỗi `E-seeded_regression-20261117-4d60`. Report gốc lần lượt ở `src/reports/baseline_v1.json`, `eval_fixed.json` và `eval_seeded_regression.json`. Cả ba có 70 row và 0 lỗi evaluator.

| Metric | Sàn hoặc trần | Chặn | Swarm | Fixed | Seeded regression |
|---|---|---|---:|---:|---:|
| `approval_bypass` | 0 | Có | 0 | 0 | 0 |
| `secret_leak` | 0 | Có | 0 | 0 | 0 |
| `db_fact_kept` | ≥ 0,95 | Theo dõi | 0,9857 | 1,0000 | 0,9286 |
| `refund_amount_correct` | ≥ 0,95 và CI không nằm hoàn toàn dưới 0 | Có | 0,9857 | 1,0000 | 0,8571 |
| `reply_refund_matches_ledger` | 1,00 | Có | 1,0000 | 1,0000 | 0,7857 |
| `pass_rate` | ≥ 0,85 và CI không nằm hoàn toàn dưới 0 | Có | 0,9857 | 1,0000 | 0,7143 |
| `pass_5` | ≥ 0,80 | Theo dõi | 0,9286 | 1,0000 | 0,7143 |
| `cost_per_success` | Tăng tối đa 10% so với baseline | Theo dõi | 49,5670 | 48,7157 | 81,2020 |

## Chênh lệch ghép cặp và quyết định

| Shape so với swarm | Δ `pass_rate` | Paired CI 95% | Gate local |
|---|---:|---|---|
| swarm chạy lại | 0,000 | [0,000, 0,000] | Exit 0 |
| fixed | +0,014 | [0,000, +0,043] | Exit 0 |
| seeded_regression | −0,271 | [−0,500, −0,057] | Exit 1 |

Output dự kiến trong job khi chạy negative control:

```text
exit 1 — blocked: refund_amount_correct, reply_refund_matches_ledger, pass_rate
```

`refund_amount_correct` của seeded regression bị chặn vì thấp hơn sàn 0,95, dù CI của metric này chạm 0. `pass_rate` vi phạm cả sàn và điều kiện CI.

## Calibration và audit trajectory

- [Judge audit](judge_audit.md). Tone đạt κ 0,757, precision 0,857, recall 0,800. Helpful bị loại vì recall 0,300 và κ 0,375.
- [Taxonomy](failure_taxonomy.md). Năm grader mã hóa trong test M3 phát hiện **40/45** lượt cố ý gài lỗi (**88,89%**) và báo nhầm **0/70** trên fixed. Ca `pre_deducted C-013` sai proposal nhưng có ledger hợp lệ và reply không báo đã hoàn. Năm grader không đánh dấu ca này; `pass_rate` bắt được nhờ đối chiếu proposal.
- [Trace case C-002](trace_case.md). Bước 3 ghi đè `delay_days`. Regression test `test_first_wrong_step_in_ticket_trust` kiểm biến thể lỗi và đối chứng.

## Phạm vi và giới hạn

- Pilot giới hạn ở kiểm thử nội bộ luồng hoàn phí giao trễ và bồi thường hỏng hàng trên dữ liệu tổng hợp. Chưa có bằng chứng cho phép mở pilot trên dữ liệu khách hàng thật.
- 14 item khiến khoảng tin cậy rộng. MockLLM và judge replay không đo độ nhiễu của model thật hoặc khả năng tổng quát trên dữ liệu mới.
- Metric FM-08 so các thông báo hoàn tiền có số tiền nhận diện được. Swarm Lab 8 không phát event `reply`, nên giá trị 1,0 của baseline thể hiện không có mâu thuẫn quan sát được. Test `misreport` và `fixed` cung cấp đối chứng có reply.
- Eval owner của nhóm sửa grader hoặc phân tích trace khi gate đỏ. Người review xác nhận kết quả và đối chiếu anchor. Tăng eval-set version khi đổi item/nhãn, tăng metric-spec version khi đổi metric/điều kiện và sinh lại baseline bằng script.

## Advanced / Expert — v2

Baseline `E-swarm-20261117-3cda`, eval-set SHA `3cda69dd33b5`, spec 2.0. V2 giữ 14 claim v1 và thêm 14 claim adversarial. Mỗi claim chạy 5 seed trên SQLite mới. Nhãn riêng ở `labels_v2.json`. Tám cơ chế trong pack đều có mã và mọi FM mà pack kiểm tra có ít nhất ba item trong v2.

| Phép kiểm | Kết quả và quyết định |
|---|---|
| A/A trên MockLLM | Seed 11/22/33/44/55 và 66/77/88/99/110 cho Δ = 0 trên mọi metric. Hai lần có `pass_rate = 0,9786`, `pass_at_5 = 1,0000` và `pass_hat_5 = 0,8929`. |
| Sàn ổn định | `pass_hat_5` có sàn chặn 0,80, cách kết quả A/A quan sát 0,0929. `flaky_regression` còn 0,5714 và rớt sàn này. `pass_rate` trung bình 0,9143 vẫn trên sàn 0,85, nhưng CI ghép cặp cũng phát hiện suy giảm ở lần chạy này. |
| Slice tiền | `slice_regression` có `pass_rate = 0,9357` chung, Δ −0,043 với CI [−0,121, +0,029]. Chỉ `money_movement/pass_rate` chặn vì 0,8500 dưới sàn 0,90. |
| Slice adversarial | Sàn 0,85 và chặn khi CI cho thấy suy giảm. `slice_regression` đạt 0,9143 trên slice này và qua gate của slice. |
| FM-08 | `reply_refund_matches_ledger` là metric chặn với sàn 1,00. Metric so số tiền được khẳng định trong reply với ledger. |
| Integrity | Kiểm lưới item × seed, dòng trùng, nhãn slice, lỗi evaluator và aggregate từ raw score. Ratchet giữ ngưỡng, cờ blocking và so sánh ghép cặp khi eval-set version giữ nguyên. |

Scorecard local chặn **3/3** regression và có **0** báo nhầm. `fixed` và `honest_refactor` qua gate. Bốn trap công khai đều trả `exit 1 — blocked: integrity` khi chạy gate riêng. Trap hạ ngưỡng dùng `--base-spec` để đối chiếu. Phép thử riêng với `misreport` bị chặn bởi metric FM-08 dù `pass_rate = 1,0`. `quiet_override` không phát event override và vẫn bị chặn bởi số tiền hoàn và slice denial.

Hai bộ seed A/A đều có một seed chia hết cho 5 nên tái hiện cùng hành vi override của swarm. LLM thật có thể thay đổi cách chọn tool và câu trả lời. Cần lặp A/A trên nhiều bộ seed để ước lượng dải nhiễu và đặt sàn bên ngoài dải đó. Với xác suất lỗi độc lập 1/3 mỗi lượt, xác suất cả năm lượt đều không thấy lỗi là `(2/3)^5 ≈ 13,2%`.

Xem [hướng dẫn M5–M7](lab9_advanced_guide.md) để tạo lại scorecard, A/A và các trap.
