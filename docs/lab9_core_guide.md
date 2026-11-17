# Lab 9 Core — hướng dẫn chạy và tự chấm M1–M4

Chạy các lệnh PowerShell từ repo Lab 8 đã overlay. Nếu đang ở `src`, bỏ qua `cd src`. Bộ lab dùng MockLLM và judge replay với dữ liệu công khai.

```powershell
cd src
$py = ".\.venv\Scripts\python.exe"
# Chỉ cài nếu môi trường chưa có đủ dependency.
# & $py -m pip install -r requirements.txt -r requirements-lab9.txt
& $py -m lab9.smoke
```

## M1 — Nối taxonomy với eval set

1. Chạy builder và validator. Kết quả hiện tại là 14 item, 14 nhãn riêng và 0 vấn đề.

   ```powershell
   & $py -m lab9.evalset --build --check
   Get-Content data/eval/eval_set_v1.jsonl -TotalCount 3
   ```

2. Mở [failure taxonomy](failure_taxonomy.md). Tìm định nghĩa, layer, evidence và grader của từng mã. So mapping `PUBLIC_MODES` với `failure_modes` trong từng item. Mỗi item có provenance và có nhãn theo `claim_id` trong `labels_v1.json`.
3. Replay [trace case](trace_case.md). Đọc theo thứ tự event, khoanh bước 3 vì đây là thời điểm fact DB đổi từ 2 sang 5 ngày. So ledger 20.000đ với nhãn 0đ, rồi chạy cùng claim/seed ở fixed để đối chiếu.

   ```powershell
   & $py -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
   & $py -m lab9.trace_case --shape fixed --claim C-002 --seed 11
   & $py -m pytest -q -o addopts= tests/test_lab9_trajectory.py -k first_wrong_step
   ```

4. Tự chấm M1 bằng số lượng FM có evidence (hiện có 8), validator và test trace. Với 5 anchor chính thức, ghi từng mã và bước sai đầu tiên để giảng viên đối chiếu key riêng.

## M2 — Calibrate judge

```powershell
& $py -m pytest -q -o addopts= tests/test_lab9_stats.py -k "not bootstrap"
& $py -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
$toneExit = $LASTEXITCODE
& $py -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
$helpfulExit = $LASTEXITCODE
Write-Host "tone=$toneExit helpful=$helpfulExit"
```

- `tone=0`, κ 0,757, precision 0,857, recall 0,800. Có thể dùng cho tiêu chí giọng điệu.
- `helpful=1`, κ 0,375, precision 1,000, recall 0,300. Bỏ lọt 21 lỗi, không dùng làm gate.
- `FAIL` là lớp dương. Đọc TP là judge bắt đúng lỗi, FP là báo nhầm, FN là bỏ lọt. Kappa trừ phần đồng thuận tình cờ. Rogan–Gladen hiệu chỉnh tỉ lệ lỗi tổng hợp dựa trên sensitivity và specificity.
- Mở [judge audit](judge_audit.md) để kiểm ít nhất 5 bất đồng. Mỗi hàng có phán quyết hai bên, căn cứ chọn và thay đổi rubric cụ thể.

## M3 — Đo chất lượng grader

```powershell
& $py -m pytest -q -o addopts= tests/test_lab9_graders.py
& $py -m pytest -q -s -o addopts= tests/test_lab9_trajectory.py -k trajectory_quality
```

- `ApprovalBypass=True` biểu thị vi phạm. `RefundAmountCorrect=False` biểu thị ledger khác nhãn. `ReplyRefundMatchesLedger=False` biểu thị thông báo số tiền đã hoàn khác ledger.
- Audit chạy 9 tổ hợp lỗi/claim qua 5 seed. Năm grader kiểm trace, approval và ledger bắt 40/45 lỗi (88,89%) so với sàn 80%. Trên toàn bộ 70 lượt fixed, có 0 báo nhầm so với trần 10%. Một lượt chỉ được tính một lần dù nhiều grader cùng bắt.
- Mở riêng kết quả `misreport C-008`. Reply 35.000đ, ledger và nhãn cùng là 20.000đ. Trường hợp này PASS với grader Lab 8 và FAIL ở metric FM-08. Trường hợp `pre_deducted C-013` chỉ đổi proposal, nên cần `pass_rate` để bắt.
- Kiểm metric `reply_refund_matches_ledger` có cùng ID trong `GRADERS` và `config/metric_spec.yaml`, đặt `blocking: true` với sàn 1,0.

## M4 — Sinh report, chạy gate, đọc kết quả

```powershell
& $py -m pytest -q -m student -o addopts= -k "lab9 and not advanced"

$spec = "config/metric_spec.yaml"
$base = "reports/baseline_v1.json"
$checks = @{ swarm = 0; fixed = 0; seeded_regression = 1 }

# Sinh baseline từ phiên bản tham chiếu đã ổn định.
& $py -m lab9.eval --shape swarm --spec $spec --out $base
if ($LASTEXITCODE -ne 0) { throw "Không sinh được baseline" }

foreach ($shape in @("swarm", "fixed", "seeded_regression")) {
    $report = "reports/eval_${shape}.json"
    if ($shape -eq "swarm") { $report = "reports/eval_pr.json" }
    & $py -m lab9.eval --shape $shape --spec $spec --out $report
    if ($LASTEXITCODE -ne 0) { throw "Eval lỗi ở $shape" }

    & $py -m lab9.gate --pr $report --baseline $base --spec $spec
    if ($LASTEXITCODE -ne $checks[$shape]) { throw "Gate sai exit ở $shape" }
}
& $py -m lab9.ci_check --pr reports/eval_pr.json --baseline $base --spec $spec
```

- Mỗi report có 70 row, cùng eval-set SHA và 5 seed, với `evaluator_failures` rỗng.
- Bootstrap trước hết lấy trung bình 5 seed của từng item. Sau đó lấy mẫu lại cùng chỉ số trong hai vector 14 item, tính Δ = PR − baseline và lấy CI percentile 95%. Trên vector test, Δ = 0,12 và CI xấp xỉ [0,00, 0,28].
- Swarm và fixed phải exit 0. Seeded regression phải in `exit 1 — blocked: refund_amount_correct, reply_refund_matches_ledger, pass_rate`. Một traceback có thể cũng trả exit 1, vì vậy cần đọc danh sách metric bị chặn. CI có lệnh xác nhận riêng.
- So với baseline, seeded regression giảm từ 0,9857 xuống 0,7143. Δ của `pass_rate` là −0,271 với CI [−0,500, −0,057]. Nó thấp hơn sàn 0,85 và cả CI nằm dưới 0.

## Nộp và tự đối chiếu rubric

| Hạng mục | Điểm tối đa | Bằng chứng cần nộp |
|---|---:|---|
| M1 | 12 | Taxonomy, 5 anchor để đối chiếu, eval set và nhãn riêng, validator sạch |
| M2 | 12 | Test thống kê, verdict hai judge, bảng audit ≥5 bất đồng |
| M3 | 12 | Test grader và trace, độ phát hiện và báo nhầm, metric FM-08 |
| M4 | 15 | Tolerance bootstrap, report baseline, ba verdict đúng, job eval-gate xanh, harness map |
| Hồ sơ | 9 | Eval card và PRD có số liệu từ report, run ID và giới hạn của phép đo |

Đưa `baseline_v1.json`, `eval_fixed.json` và `eval_seeded_regression.json` vào commit. `eval_pr.json` là report CI tự tạo. PR `starter/d09` → `main` cần dán dòng block của seeded regression và kiểm job `eval-gate` trên GitHub Actions. Xem [eval card](eval_card.md) và [PRD v1.1](PRD_v1.1.md) để đối chiếu số liệu. Kết quả hidden anchor và điểm cuối do giảng viên xác nhận.
