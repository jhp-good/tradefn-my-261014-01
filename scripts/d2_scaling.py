"""2일차 실습 A5 — revenue 스케일 비교(로그 → Min-Max · 표준화). 특성 파일에는 넣지 않는다.

실행: uv run python scripts/d2_scaling.py
입력: data/checkpoints/d2_start.xlsx 시트 buyers의 revenue(읽기만) — 정제 CSV 25열에는 revenue가 없다
결과: workbench/day2/outputs/scaling.md (비교 표만)

계산
  log_rev  = ln(revenue)                                  revenue 빈칸(18곳)은 제외, 132곳
  minmax   = (log_rev − min) ÷ (max − min)                → 0~1
  zscore   = (log_rev − 평균) ÷ 표준편차(모집단, ddof=0)    → StandardScaler와 같은 정의
  대조용    로그 없이 원값에 바로 Min-Max · 표준화
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path("data/checkpoints/d2_start.xlsx")
OUT = Path("workbench/day2/outputs/scaling.md")

raw = pd.read_excel(SRC, sheet_name="buyers")
rev = raw.set_index("buyer_id")["revenue"].dropna().astype(float)
n_missing = int(raw["revenue"].isna().sum())

log_rev = np.log(rev)
minmax = lambda s: (s - s.min()) / (s.max() - s.min())
zscore = lambda s: (s - s.mean()) / s.std(ddof=0)

t = pd.DataFrame({
    "revenue": rev,
    "log_rev": log_rev,
    "minmax_log": minmax(log_rev),
    "z_log": zscore(log_rev),
    "minmax_raw": minmax(rev),
    "z_raw": zscore(rev),
})

median = rev.median()
pick = {
    "최소": rev.idxmin(),
    "중앙값 근처": (rev - median).abs().idxmin(),
    "최대": rev.idxmax(),
}
rows = "\n".join(
    f"| {label} | {bid} | {t.revenue[bid]:,.0f} | {t.log_rev[bid]:.4f} | {t.minmax_log[bid]:.4f} | "
    f"{t.z_log[bid]:+.4f} | {t.minmax_raw[bid]:.4f} | {t.z_raw[bid]:+.4f} |"
    for label, bid in pick.items())
ratio = rev.max() / rev.min()
below_01_raw = int((t.minmax_raw < 0.1).sum())
below_01_log = int((t.minmax_log < 0.1).sum())

report = f"""# revenue 스케일 비교 (2일차)

- 입력: `{SRC.as_posix()}` 시트 `buyers`의 `revenue`(USD, 읽기만). 빈칸 {n_missing}곳은 빼고 {len(rev)}곳으로 계산했다.
- 코드: `scripts/d2_scaling.py`. 이 표는 비교용이다. **정규화 열은 특성 파일(`d2_buyers_clean.csv`)에 넣지 않았다.**
- 로그는 자연로그 ln이다. 표준화는 (x − 평균) ÷ 표준편차(모집단, ddof=0)이고, Min-Max는 (x − 최소) ÷ (최대 − 최소)다.
- 중앙값 근처: {len(rev)}곳의 중앙값 {median:,.0f}에 가장 가까운 바이어다.

## 비교 표

| 위치 | buyer_id | revenue (USD) | ln(revenue) | 로그 → Min-Max | 로그 → 표준화 | (대조) 원값 Min-Max | (대조) 원값 표준화 |
|---|---|---|---|---|---|---|---|
{rows}

## 읽는 법

- 최대 매출 ÷ 최소 매출 = {ratio:,.1f}배.
- 원값에 바로 Min-Max를 하면 극단값 한 곳이 범위를 정하고, 나머지는 0 쪽으로 눌린다. 중앙값 근처 바이어가 {t.minmax_raw[pick['중앙값 근처']]:.4f}이고, {len(rev)}곳 중 {below_01_raw}곳이 0.1 미만이다.
- 로그를 먼저 취하면 중앙값 근처 바이어가 {t.minmax_log[pick['중앙값 근처']]:.4f}로 올라온다. 0.1 미만은 {below_01_log}곳이다.
- 로그 뒤 표준화한 값의 평균은 {t.z_log.mean():.4f}, 표준편차는 {t.z_log.std(ddof=0):.4f}이다. 최대 · 최소 바이어는 각각 {t.z_log[pick['최대']]:+.2f} · {t.z_log[pick['최소']]:+.2f} 표준편차에 있다.
"""
OUT.write_text(report, encoding="utf-8")
print(report)
