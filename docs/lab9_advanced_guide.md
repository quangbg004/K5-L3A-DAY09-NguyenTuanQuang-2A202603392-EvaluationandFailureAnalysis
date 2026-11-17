# Lab 9 Advanced / Expert — chạy và tự chấm M5–M7

Chạy PowerShell trên nhánh `lab9/starter`. Từ thư mục gốc của repo:

```powershell
cd src
# Nếu chưa có môi trường: python -m venv .venv
$py = ".\.venv\Scripts\python.exe"
# Cài dependency khi chuẩn bị môi trường:
# & $py -m pip install -r requirements.txt -r requirements-lab9.txt
$spec = "config/metric_spec_v2.yaml"
$base = "reports/baseline_v2.json"
```

## M5 — Eval set và slice

```powershell
& $py -m lab9.evalset --v2 --build
& $py -m lab9.evalset --v2 --check
& $py -m lab9.eval --shape swarm --spec $spec --out $base
& $py -m lab9.eval --shape slice_regression --spec $spec --out reports/eval_slice_regression.json
& $py -m lab9.gate --spec $spec --pr reports/eval_slice_regression.json --baseline $base
```

Build tạo 28 item và 28 nhãn riêng, check báo 0 vấn đề. Baseline có 140 lượt. Gate của `slice_regression` trả **exit 1** vì `money_movement/pass_rate` đạt 0,8500 dưới sàn 0,90. Pass rate chung vẫn đạt 0,9357.

## M6 — Độ ổn định theo seed

```powershell
& $py -m pytest -q -m student -o addopts= -k advanced
& $py -m lab9.mutation --spec $spec --aa 66,77,88,99,110
& $py -m lab9.mutation --spec $spec --baseline $base --base-spec $spec
```

`pass_at_5` đo xác suất có ít nhất một lượt đỗ. `pass_hat_5` đo xác suất cả năm lượt đỗ. Nếu một item chỉ đỗ bốn trong năm lượt thì `pass_hat_5` bằng 0 cho item đó. A/A chạy cùng swarm trên hai bộ seed và cho Δ bằng 0. Scorecard cần chặn **3/3 regression**, báo nhầm **0**, và liệt kê `pass_hat_5` trong các metric chặn `flaky_regression`.

## M7 — Integrity và ratchet

```powershell
& $py -m lab9.gate --spec $spec --pr $base --baseline $base --base-spec $spec
& $py -m lab9.traps --spec $spec --pr reports/eval_slice_regression.json --baseline $base
```

Baseline so với chính nó trả exit 0. Runner `lab9.traps` in bốn câu lệnh để kiểm tra riêng từng trap và trả exit 0 khi cả bốn đều bị chặn. Chạy từng câu lệnh đã in để thấy `exit 1 — blocked: integrity`. Với trap hạ ngưỡng, giữ `--base-spec config/metric_spec_v2.yaml` để gate so hai spec.

## GitHub Actions và nộp bài

Vào **Actions → lab9-eval-gate → Run workflow**, chọn **lab9/starter**. Mở lượt chạy và kiểm hai job **eval-gate** và **eval-gate-v2**. Job v2 chạy test Advanced, kiểm eval set, chạy scorecard và thử bốn trap. Khi nộp, lưu URL CI cùng output A/A, scorecard và các verdict trap. Nếu mở PR, dùng `lab9/starter` làm nhánh compare và `main` làm base.
