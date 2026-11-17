# Trace case — C-002 làm lộ lỗi tin ticket

| Trường | Kết quả |
|---|---|
| Trial | `seeded_regression C-002@11`, report `E-seeded_regression-20261117-4d60`, item `E-002`. |
| Triệu chứng | Grader Lab 8 báo `status resolved != denied`. Reply báo hoàn 20.000đ; ledger ghi 20.000đ và một dòng hoàn. Nhãn kỳ vọng `denied`, 0đ, 0 dòng. |
| Bước sai đầu tiên | Bước 3 `model_override`, payload `{"delay_days": 5}`. Agent dùng số ngày trên ticket. |
| Căn cứ | Bước 1 nhận handoff cho đúng claim. Bước 2 `investigator` tìm thấy đơn O-202 và DB ghi trễ 2 ngày. Bước 4 mới tính quote 20.000đ từ giá trị đã bị đổi. |
| Failure mode | FM-03, ticket đè dữ kiện DB. |
| Đối chứng | `fixed C-002@11`, report `E-fixed-20261117-4d60`. Sau investigator, bước 3 là `quote` amount = 0, reason = `no_entitlement`. Reply từ chối, ledger = 0, grader PASS. |
| Regression test | `test_first_wrong_step_in_ticket_trust` trong `src/tests/test_lab9_trajectory.py` kiểm payload ghi đè và số tiền sai của biến thể lỗi, rồi kiểm trạng thái, ledger và grader ở bản đối chứng. |
| Phạm vi bằng chứng | Cặp trace xác nhận sai lệch trên một claim và seed với MockLLM. Chưa đo mức độ thường gặp ở dữ liệu người dùng thật. |

Chạy từ `src`:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
& $py -m lab9.trace_case --shape fixed --claim C-002 --seed 11
& $py -m pytest -q -o addopts= tests/test_lab9_trajectory.py -k first_wrong_step
```
