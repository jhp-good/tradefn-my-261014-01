"""2일차 실습 A — buyers 시트를 정제 규칙대로 정리한다(원본은 읽기만).

근거: workbench/day2/rules/정제규칙.md (1–7칸) · workbench/day2/outputs/profile.md (진단)
실행: uv run python scripts/clean_buyers.py
결과: workbench/day2/outputs/d2_buyers_clean.csv (150행 × 25열) · workbench/day2/outputs/dq_report.md

정리 규칙
  1 통화      usd · US$ → USD, euro → EUR, yen → JPY, RMB → CNY. 매핑에 없는 표기는 멈춘다
  2 숫자      공백 · 콤마 · 통화 글자 제거, 끝의 k = ×1,000 → amt_num(잔액) · 구간 *_num
  3 결측      fin_missing = 유동자산 · 유동부채 · 총부채 · 자기자본 · 매출 중 하나라도 빈칸.
              비율 4열을 먼저 계산하고, 빈칸을 대체 전 150행의 그 열 중위수로 채운다(자본잠식 D/E는 빈칸 유지).
              분모 0 · 원래 빈칸인 연체 열은 채우지 않는다
  4 단위 의심 USD 환산 잔액 > credit_limit_usd × 10 → unit_flag = 1, amt_num ÷ 1,000
  5 자본잠식  equity ≤ 0 → neg_equity = 1, debt_to_equity 빈칸
  6 국가위험  oecd_crc '-' · 빈칸 → country_risk = 0, crc_unclassified = 1
  7 환율      fx_at_ref의 ref_date 2026-08-31 행만. fx_chg_30d = chg_30d,
              fx_chg_30d_lag30 = fx_krw_daily.csv의 (AsOf−30일) ÷ (AsOf−60일) − 1(휴일이면 직전 관측일)
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path("data/checkpoints/d2_start.xlsx")
FX_DAILY = Path("workbench/day2/data/fx_krw_daily.csv")
OUT = Path("workbench/day2/outputs")
ASOF = pd.Timestamp("2026-08-31")

CCY_MAP = {"USD": "USD", "usd": "USD", "US$": "USD", "EUR": "EUR", "euro": "EUR",
           "JPY": "JPY", "yen": "JPY", "CNY": "CNY", "RMB": "CNY"}
FX_KEY = {"USD": "USD", "EUR": "EUR", "CNY": "CNY", "JPY": "JPY100"}  # fx_at_ref의 ccy
FX_PER = {"USD": 1, "EUR": 1, "CNY": 1, "JPY": 100}                     # 엔화는 100엔 단위
DAILY_COL = {"USD": "usd_krw", "EUR": "eur_krw", "CNY": "cny_krw", "JPY": "jpy100_krw"}
AR = ["ar_balance", "ar_current", "ar_1_30", "ar_31_60", "ar_61_90", "ar_91p"]
BUCKETS = AR[1:]
FIN_FLAG = ["current_assets", "current_liabilities", "total_liabilities", "equity", "revenue"]
RATIOS = ["current_ratio", "debt_to_equity", "dso_buyer", "op_margin"]
COLUMNS = ["buyer_id", "payment_method", "ccy_clean", "amt_num", "ar_balance_usd",
           "pct_current", "pct_ar_31p", "pct_91plus", "max_dpd", "avg_days_late", "late_ratio",
           "dpd_trend", "dispute_ratio", "current_ratio", "debt_to_equity", "dso_buyer", "op_margin",
           "fin_missing", "neg_equity", "country_risk", "crc_unclassified", "unit_flag",
           "fx_chg_30d", "fx_chg_30d_lag30", "late_30d"]


def parse_amount(v):
    """규칙 2: 원천 금액 표기 → float. 못 읽으면 None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(",", "")
    t = re.sub(r"(?i)usd|us\$|eur|jpy|cny|rmb", "", t).strip()
    mult = 1000 if t.lower().endswith("k") else 1
    try:
        return float(t.rstrip("kK").strip()) * mult
    except ValueError:
        return None


def div(a, b):
    """분모가 0이거나 빈칸이면 빈칸(규칙 3: 0으로 채우지 않는다)."""
    return a / b.where(b != 0)


def has_text(s):
    return int(s.map(lambda v: isinstance(v, str)).sum())


# ---- 읽기(원본은 읽기만) ----
raw = pd.read_excel(SRC, sheet_name="buyers", dtype=object)
fx_ref = pd.read_excel(SRC, sheet_name="fx_at_ref")
fx_daily = pd.read_csv(FX_DAILY, encoding="utf-8-sig", parse_dates=["date"]).set_index("date").sort_index()
assert len(raw) == 150 and raw["buyer_id"].is_unique

df = pd.DataFrame({"buyer_id": raw["buyer_id"], "payment_method": raw["payment_method"]})

# ---- 1 통화 ----
unknown = sorted(set(raw["currency"]) - set(CCY_MAP))
if unknown:
    raise SystemExit(f"매핑표에 없는 통화 표기: {unknown} — 규칙 1칸 매핑에 추가 후 다시 실행")
df["ccy_clean"] = raw["currency"].map(CCY_MAP)

# ---- 2 숫자 변환 ----
num = pd.DataFrame({c: raw[c].map(parse_amount) for c in AR}).astype(float)
failed = {c: raw.loc[num[c].isna() & raw[c].notna(), "buyer_id"].tolist() for c in AR}
if any(failed.values()):
    raise SystemExit(f"숫자로 못 읽은 칸: {failed}")
bucket_sum = num[BUCKETS].sum(axis=1)

# ---- 7 환율(기준일 행만) ----
fx = fx_ref[fx_ref["ref_date"] == ASOF].set_index("ccy")
assert len(fx) == 4, "fx_at_ref에 기준일 2026-08-31 행이 4통화 모두 있어야 한다"
krw_per_unit = df["ccy_clean"].map(lambda c: fx.loc[FX_KEY[c], "krw_close"] / FX_PER[c])
usd_krw = fx.loc["USD", "krw_close"]
to_usd = krw_per_unit / usd_krw

df["fx_chg_30d"] = df["ccy_clean"].map(lambda c: fx.loc[FX_KEY[c], "chg_30d"])
t30, t60 = ASOF - pd.Timedelta(days=30), ASOF - pd.Timedelta(days=60)
obs30, obs60 = fx_daily.loc[:t30].index[-1], fx_daily.loc[:t60].index[-1]  # 휴일이면 직전 관측일
lag30 = {c: fx_daily.loc[obs30, col] / fx_daily.loc[obs60, col] - 1 for c, col in DAILY_COL.items()}
df["fx_chg_30d_lag30"] = df["ccy_clean"].map(lag30)

# ---- 4 단위 의심(USD 환산 후 판정 → ÷1,000) ----
credit_limit = raw["credit_limit_usd"].astype(float)
usd_before = num["ar_balance"] * to_usd
df["unit_flag"] = (usd_before > credit_limit * 10).astype(int)
df["amt_num"] = num["ar_balance"].where(df["unit_flag"] == 0, num["ar_balance"] / 1000)
df["ar_balance_usd"] = df["amt_num"] * to_usd

# 연령 구간 비율 — 분모는 구간 합(합이 1이 되도록). 잔액 0이면 빈칸
df["pct_current"] = div(num["ar_current"], bucket_sum)
df["pct_ar_31p"] = div(num[["ar_31_60", "ar_61_90", "ar_91p"]].sum(axis=1), bucket_sum)
df["pct_91plus"] = div(num["ar_91p"], bucket_sum)

# ---- 연체 행동 ----
q = raw[["max_dpd", "avg_days_late_12m", "invoices_12m", "late_invoices_12m",
         "dispute_cnt_12m", "avg_dpd_last3m", "avg_dpd_prev3m"]].astype(float)
df["max_dpd"] = q["max_dpd"]
df["avg_days_late"] = q["avg_days_late_12m"]
df["late_ratio"] = div(q["late_invoices_12m"], q["invoices_12m"])
df["dpd_trend"] = q["avg_dpd_last3m"] - q["avg_dpd_prev3m"]  # +면 최근 악화
df["dispute_ratio"] = div(q["dispute_cnt_12m"], q["invoices_12m"])

# ---- 3 · 5 재무 비율 ----
fin = raw[["current_assets", "current_liabilities", "total_liabilities", "equity",
           "accounts_receivable", "revenue", "operating_income"]].astype(float)
df["fin_missing"] = fin[FIN_FLAG].isna().any(axis=1).astype(int)
df["neg_equity"] = (fin["equity"] <= 0).astype(int)
df["current_ratio"] = div(fin["current_assets"], fin["current_liabilities"])
df["debt_to_equity"] = div(fin["total_liabilities"], fin["equity"].where(fin["equity"] > 0))
df["dso_buyer"] = div(fin["accounts_receivable"], fin["revenue"]) * 365
df["op_margin"] = div(fin["operating_income"], fin["revenue"])

ratio_before = df[RATIOS].copy()
medians = ratio_before.median()  # 대체 전 150행의 그 열 중위수
for c in RATIOS:
    fill_mask = df[c].isna()
    if c == "debt_to_equity":
        fill_mask &= df["neg_equity"] == 0  # 자본잠식 빈칸은 그대로
    df.loc[fill_mask, c] = medians[c]

# ---- 6 국가위험 ----
crc = pd.to_numeric(raw["oecd_crc"], errors="coerce")
df["crc_unclassified"] = crc.isna().astype(int)
df["country_risk"] = crc.fillna(0).astype(int)

df["late_30d"] = raw["late_30d"].astype(int)
df = df[COLUMNS]

# ---- 검사 ----
assert len(df) == 150 and df["buyer_id"].is_unique
assert df.columns[0] == "buyer_id" and df.columns[-1] == "late_30d" and len(df.columns) == 25
assert df["ccy_clean"].isin(["USD", "EUR", "JPY", "CNY"]).all()
assert df.loc[df["neg_equity"] == 1, "debt_to_equity"].isna().all()

OUT.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT / "d2_buyers_clean.csv", index=False, encoding="utf-8")

# ---- 전·후 비교 보고서 ----
mismatch = df.assign(diff=df["amt_num"] - bucket_sum)[lambda d: d["diff"].abs() > 0.5]
fmt = lambda x: "빈칸" if pd.isna(x) else f"{x:,.4f}"
rows_ccy = "\n".join(f"| {k} | {v} |" for k, v in raw["currency"].value_counts().items())
rows_ccy_after = "\n".join(f"| {k} | {v} |" for k, v in df["ccy_clean"].value_counts().items())
text_cells_before = sum(has_text(raw[c]) for c in AR)
unit_rows = "\n".join(
    f"| {raw.buyer_id[i]} | {raw.currency[i]} | `{raw.ar_balance[i]}` | {usd_before[i]:,.2f} | "
    f"{credit_limit[i]:,.0f} | {usd_before[i] / credit_limit[i]:,.1f} | {df.amt_num[i]:,.2f} | {df.ar_balance_usd[i]:,.2f} |"
    for i in df.index[df["unit_flag"] == 1])
fill_rows = "\n".join(
    f"| {c} | {int(ratio_before[c].isna().sum())} | {fmt(medians[c])} | "
    f"{int(ratio_before[c].isna().sum() - df[c].isna().sum())} | {int(df[c].isna().sum())} |" for c in RATIOS)
na_rows = "\n".join(f"| {c} | {int(df[c].isna().sum())} |"
                    for c in ["pct_current", "pct_ar_31p", "pct_91plus", "avg_days_late",
                              "late_ratio", "dpd_trend", "dispute_ratio"])
mismatch_rows = "\n".join(
    f"| {r.buyer_id} | `{raw.ar_balance[i]}` | {r.amt_num:,.2f} | {bucket_sum[i]:,.2f} | {r['diff']:,.2f} |"
    for i, r in mismatch.iterrows()) or "| (없음) | | | | |"
fx_rows = "\n".join(
    f"| {c} | {fx.loc[FX_KEY[c], 'krw_close']:,.2f} | {fx.loc[FX_KEY[c], 'chg_30d']:.4f} | "
    f"{fx_daily.loc[obs30, DAILY_COL[c]]:,.2f} | {fx_daily.loc[obs60, DAILY_COL[c]]:,.2f} | {lag30[c]:.4f} |"
    for c in ["USD", "EUR", "CNY", "JPY"])

report = f"""# 데이터 품질 전·후 비교 — buyers (2일차)

- 입력: `{SRC.as_posix()}` 시트 `buyers` (읽기만) · `{FX_DAILY.as_posix()}`
- 규칙: `workbench/day2/rules/정제규칙.md` 1–7칸 · 코드: `scripts/clean_buyers.py`
- 결과: `workbench/day2/outputs/d2_buyers_clean.csv` — {len(df)}행 × {len(df.columns)}열, buyer_id 중복 {int(df.buyer_id.duplicated().sum())}
- 기준일(AsOf): {ASOF.date()} · 이 보고서의 숫자는 모두 위 스크립트가 낸 값이다

## 1. 전·후 건수

| 항목 | 전(원천) | 후(정제) | 규칙 |
|---|---|---|---|
| 통화 표기 종류 | {raw.currency.nunique()} | {df.ccy_clean.nunique()} | 1 |
| 비표준 통화 표기 행 | {int((~raw.currency.isin(['USD', 'EUR', 'JPY', 'CNY'])).sum())} | 0 | 1 |
| 금액 칸 중 글자 섞인 칸(ar_* 6열) | {text_cells_before} | 0 | 2 |
| 재무 결측이 있는 바이어(사전 5항목 기준) | {int(df.fin_missing.sum())} | {int(df.fin_missing.sum())} (fin_missing=1로 표시) | 3 |
| 비율 4열의 빈칸 합 | {int(ratio_before.isna().sum().sum())} | {int(df[RATIOS].isna().sum().sum())} (자본잠식 D/E만 남음) | 3·5 |
| 단위 의심(USD 잔액 > 한도 × 10) | {int(df.unit_flag.sum())} | 0 (÷1,000, unit_flag=1 유지) | 4 |
| 자본잠식(equity ≤ 0) | {int(df.neg_equity.sum())} | {int(df.neg_equity.sum())} (neg_equity=1, D/E 빈칸) | 5 |
| 국가위험 `-` 표기 | {int((raw.oecd_crc.astype(str) == '-').sum())} | 0 (crc_unclassified=1, country_risk=0) | 6 |

통화 표기 — 전

| currency | 행 |
|---|---|
{rows_ccy}

통화 표기 — 후

| ccy_clean | 행 |
|---|---|
{rows_ccy_after}

## 2. 단위 의심 처리

| buyer_id | 통화 | 원천 ar_balance | 처리 전 USD | 한도 | 배수 | amt_num(÷1,000) | ar_balance_usd |
|---|---|---|---|---|---|---|---|
{unit_rows}

## 3. 결측 채우기(비율 열, 대체 전 150행 중위수)

| 열 | 대체 전 빈칸 | 중위수(대체값) | 채운 칸 | 남은 빈칸 |
|---|---|---|---|---|
{fill_rows}

- debt_to_equity의 남은 빈칸은 자본잠식 바이어({', '.join(df.buyer_id[df.neg_equity == 1])})다. 규칙 5칸에 따라 채우지 않는다.

## 4. 채우지 않은 빈칸(분모 0 · 원래 빈칸)

| 열 | 빈칸 |
|---|---|
{na_rows}

- pct_* 열은 잔액(구간 합)이 0이면 빈칸이다. late_ratio · dispute_ratio는 invoices_12m이 0이면 빈칸이다.
- avg_days_late · dpd_trend는 원천이 빈칸이면 빈칸이다(규칙 3칸).

## 5. 확인 필요 — 잔액과 구간 합이 다른 바이어

| buyer_id | 원천 ar_balance | amt_num | 구간 합 | 차이 |
|---|---|---|---|---|
{mismatch_rows}

- pct_* 열은 분모로 구간 합을 쓰므로 비율의 합은 1이다. 다만 amt_num · ar_balance_usd는 원천 잔액을 따른다.

## 6. 환율(기준일 {ASOF.date()})

lag30의 관측일은 30일 전 {obs30.date()}, 60일 전 {obs60.date()}다.

| 통화 | krw_close | fx_chg_30d | 30일 전 | 60일 전 | fx_chg_30d_lag30 |
|---|---|---|---|---|---|
{fx_rows}

## 7. 검사

- 행 150 · buyer_id 고유 · 첫 열 buyer_id · 끝 열 late_30d · 25열: 통과(스크립트 assert)
- 원본 `data/` 수정 없음: 스크립트는 읽기만 한다. `git status`로 함께 확인한다
"""
(OUT / "dq_report.md").write_text(report, encoding="utf-8")

print(f"저장: {OUT / 'd2_buyers_clean.csv'} ({len(df)}행 × {len(df.columns)}열) · {OUT / 'dq_report.md'}")
print("unit_flag:", df.loc[df.unit_flag == 1, ["buyer_id", "amt_num", "ar_balance_usd"]].to_dict("records"))
print("neg_equity:", df.buyer_id[df.neg_equity == 1].tolist(), "| fin_missing 합:", int(df.fin_missing.sum()))
print("대체값(중위수):", medians.round(4).to_dict())
print("B001 ar_balance_usd:", round(df.loc[0, "ar_balance_usd"], 2))
