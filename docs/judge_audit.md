# Judge audit — calibration trên CSV replay

Cả hai bộ có 100 câu. `FAIL` là lớp dương. Sàn là κ ≥ 0,6, precision ≥ 0,8, recall ≥ 0,7.

| Tiêu chí | TP / FP / FN / TN | κ | Precision | Recall | Tỉ lệ lỗi quan sát → hiệu chỉnh | Quyết định |
|---|---:|---:|---:|---:|---:|---|
| tone_ok | 24 / 4 / 6 / 66 | 0,757 | 0,857 | 0,800 | 0,28 → 0,30 | PASS, dùng đánh giá giọng điệu. |
| helpful | 9 / 0 / 21 / 70 | 0,375 | 1,000 | 0,300 | 0,09 → 0,30 | FAIL, loại khỏi gate. |

`helpful` chỉ đánh FAIL ở 9/30 câu mà người chấm xem là lỗi. 21 ca bỏ lọt làm recall thấp, gồm câu trả lời lịch sự nhưng sai số tiền. Tỉ lệ sau hiệu chỉnh là ước lượng tổng hợp; các phán quyết từng case vẫn giữ nguyên.

## Bất đồng đã audit

| Case | Judge | Human | Đối chiếu và quyết định | Sửa rubric |
|---|---|---|---|---|
| H-008 | PASS | FAIL | Chọn human. Tổ hợp “em”, “nha” quá suồng sã trong ngữ cảnh CSKH này. | Thêm ví dụ phân biệt thân thiện với xưng hô suồng sã. |
| H-017 | PASS | FAIL | Chọn human theo ngữ cảnh CSV ghi nhận khách lớn tuổi. | Nêu cách xưng hô theo thông tin khách; dùng cách trung tính khi thiếu ngữ cảnh. |
| H-029 | PASS | FAIL | Chọn human. “Không cần nhắn thêm” mang giọng ra lệnh. | Chấm cả câu, kể cả mệnh lệnh đứng sau lời mở đầu lịch sự. |
| H-042 | FAIL | PASS | Chọn human. Reply ngắn, lịch sự và có đủ số tiền cùng thời điểm dự kiến. | Yêu cầu lời xin lỗi theo tình huống cụ thể. Độ dài riêng lẻ không phải tiêu chí. |
| H-051 | FAIL | PASS | Chọn human. Từ “refund” được CS LogiX chấp nhận. | Nêu thuật ngữ dịch vụ được chấp nhận và ưu tiên độ dễ hiểu. |
| HL-015 | PASS | FAIL | Chọn human. Reply báo 55.000đ, ledger ghi 40.000đ. | Bắt buộc dùng code đối chiếu số tiền với ledger trước khi chấm phần lời văn. |

H-017 phụ thuộc vào ngữ cảnh ghi trong note. Khi đánh giá lại, cần cho người chấm và judge cùng thông tin ngữ cảnh. Tập này là replay công khai; dùng tập mới có nhãn người để kiểm tra các thay đổi rubric.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
& $py -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```
