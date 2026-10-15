"""2일차: d2_start.xlsx buyers 시트 진단(읽기 전용). 원본은 고치지 않는다.

실행: uv run python scripts/d2_profile_buyers.py
"""
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

PATH = "data/checkpoints/d2_start.xlsx"
# 원천 표기를 그대로 보려고 object로 읽는다
df = pd.read_excel(PATH, sheet_name="buyers", dtype=object)
fx = pd.read_excel(PATH, sheet_name="fx_at_ref")
N = len(df)
XL = lambda i: i + 2  # 엑셀 행 번호(머리글 1행)

REGIONS = {"북미·중남미", "서유럽", "중동부유럽", "동아시아", "동남아·남아", "중동·아프리카"}
PAY = {"TT_ADV", "TT_SPLIT_30_70", "OA", "DA", "DP", "LC_SIGHT", "LC_USANCE"}
AR = ["ar_balance", "ar_current", "ar_1_30", "ar_31_60", "ar_61_90", "ar_91p"]
FIN = ["current_assets", "current_liabilities", "total_liabilities", "equity",
       "accounts_receivable", "revenue", "operating_income"]


def tdist(s):
    return s.dropna().map(lambda v: type(v).__name__).value_counts().to_dict()


def to_num(v):
    """진단용 파싱: 콤마·공백·통화문자 제거, k = ×1000. 원본은 바꾸지 않는다."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(",", "")
    t = re.sub(r"(?i)usd|us\$|eur|jpy|cny|rmb|\$|€|¥", "", t).strip()
    mult = 1000 if t.lower().endswith("k") else 1
    t = t.rstrip("kK").strip()
    try:
        return float(t) * mult
    except ValueError:
        return None


def pattern(v):
    """문자 표기 패턴 분류"""
    if not isinstance(v, str):
        return type(v).__name__
    tags = []
    if v != v.strip():
        tags.append("앞뒤공백")
    if "," in v:
        tags.append("콤마")
    if re.search(r"(?i)usd|us\$|eur|jpy|cny|rmb|[$€¥]", v):
        tags.append("통화문자")
    if re.search(r"\d\s*[kK]\s*$", v.strip()):
        tags.append("k표기")
    return "str:" + ("+".join(tags) if tags else "숫자문자")


print("shape:", df.shape, "| 완전중복행:", df.duplicated().sum())
print("\n## 열별 요약")
for c in df.columns:
    s = df[c]
    nn = s.dropna()
    blank = nn.map(lambda v: isinstance(v, str) and v.strip() == "").sum()
    print(f"{c}: null={s.isna().sum()} blank={blank} uniq={nn.nunique()} types={tdist(s)}")

print("\n## buyer_id")
bid = df["buyer_id"].astype(str)
print("형식 B### 아님:", bid[~bid.str.fullmatch(r"B\d{3}")].tolist(), "| 중복:", bid[bid.duplicated()].tolist())
print("범위 B001~B150 누락:", sorted(set(f"B{i:03d}" for i in range(1, 151)) - set(bid)))

print("\n## 범주형 표기")
for c in ["country_code", "region", "payment_method", "oecd_crc", "currency", "late_30d"]:
    print(c, df[c].map(repr).value_counts(dropna=False).to_dict())
cc = df["country_code"].astype(str)
print("country_code 3자 대문자 아님:", cc[~cc.str.fullmatch(r"[A-Z]{3}")].tolist())
print("region 허용 밖:", sorted(set(df["region"].dropna()) - REGIONS))
print("payment_method 허용 밖:", sorted(set(df["payment_method"].dropna()) - PAY))
print("country_code별 region 2개 이상:",
      df.groupby("country_code")["region"].nunique().loc[lambda x: x > 1].to_dict())

print("\n## 금액 열 표기 패턴")
P = pd.DataFrame({c: [to_num(v) for v in df[c]] for c in AR})
for c in AR:
    pat = df[c].map(pattern).value_counts().to_dict()
    bad = [(XL(i), df[c][i]) for i in df.index if df[c][i] is not None and not pd.isna(df[c][i]) and P[c][i] is None]
    print(f"{c}: 패턴={pat} | 파싱불가={bad}")
    ex = [(XL(i), repr(df[c][i])) for i in df.index if isinstance(df[c][i], str)][:12]
    print("   문자 예시:", ex)
    print(f"   파싱 후 min={P[c].min()} max={P[c].max()} 음수={(P[c] < 0).sum()}")

print("\n## 잔액 = 연령구간 합 검증 (진단용 파싱값)")
diff = P["ar_balance"] - P[AR[1:]].sum(axis=1)
bad = diff[diff.abs() > 0.5]
for i in bad.index:
    print(f"  행{XL(i)} {df.buyer_id[i]}: ar_balance={df.ar_balance[i]!r} 구간합={P.loc[i, AR[1:]].sum()} 차이={diff[i]}")
print("  불일치 건수:", len(bad))

print("\n## 단위 의심: USD 환산 잔액 > credit_limit_usd × 10")
ASOF = pd.Timestamp("2026-08-31")  # 기준일 이후(09-30) 환율은 쓰지 않는다
fx_last = fx[fx["ref_date"] == ASOF].set_index("ccy")
print(fx_last[["unit", "krw_close"]].to_string())
CCY = {"USD": "USD", "usd": "USD", "US$": "USD", "EUR": "EUR", "euro": "EUR",
       "JPY": "JPY100", "yen": "JPY100", "CNY": "CNY", "RMB": "CNY"}
usd_krw = fx_last.loc["USD", "krw_close"]


def to_usd(amt, ccy):
    k = CCY.get(str(ccy).strip())
    if amt is None or k is None:
        return None
    r = fx_last.loc[k]
    per = float(re.search(r"per (\d+)", r["unit"]).group(1))  # 'KRW per 100 JPY' → 100
    return amt * (r["krw_close"] / per) / usd_krw


usd = pd.Series([to_usd(P.ar_balance[i], df.currency[i]) for i in df.index])
lim = pd.to_numeric(df.credit_limit_usd, errors="coerce")
flag = usd > lim * 10
for i in df.index[flag]:
    print(f"  행{XL(i)} {df.buyer_id[i]} {df.currency[i]} ar_balance={df.ar_balance[i]!r} ≈USD {usd[i]:,.0f} 한도={lim[i]:,.0f} 배수={usd[i]/lim[i]:.1f}")
print("  건수:", int(flag.sum()))
print("  잔액 > 한도(1배 초과):", int((usd > lim).sum()))

print("\n## 지연·건수 열")
NUMC = ["max_dpd", "avg_days_late_12m", "invoices_12m", "late_invoices_12m", "dispute_cnt_12m",
        "avg_dpd_last3m", "avg_dpd_prev3m", "credit_limit_usd"]
Q = df[NUMC].apply(pd.to_numeric, errors="coerce")
for c in NUMC:
    q1, q3 = Q[c].quantile([.25, .75])
    hi = q3 + 3 * (q3 - q1)
    print(f"{c}: min={Q[c].min()} max={Q[c].max()} 중위={Q[c].median()} 음수={(Q[c] < 0).sum()} "
          f"정수아님={(Q[c].dropna() % 1 != 0).sum()} >Q3+3IQR({hi:g})={Q[c][Q[c] > hi].tolist()}")
print("late_invoices_12m > invoices_12m:", df.buyer_id[Q.late_invoices_12m > Q.invoices_12m].tolist())
print("dispute_cnt_12m > invoices_12m:", df.buyer_id[Q.dispute_cnt_12m > Q.invoices_12m].tolist())
print("credit_limit 값 분포:", Q.credit_limit_usd.value_counts().sort_index().to_dict())

print("\n## max_dpd ↔ 연령구간 정합")
def bucket(d):
    return None if d <= 0 else "ar_1_30" if d <= 30 else "ar_31_60" if d <= 60 else "ar_61_90" if d <= 90 else "ar_91p"
for i in df.index:
    d, b = Q.max_dpd[i], bucket(Q.max_dpd[i])
    if b and not (P[b][i] and P[b][i] > 0):
        print(f"  행{XL(i)} {df.buyer_id[i]} max_dpd={d} 인데 {b}={df[b][i]!r}")
    later = [x for x in AR[2:] if b is None or AR.index(x) > AR.index(b)]
    over = [x for x in later if P[x][i] and P[x][i] > 0]
    if over:
        print(f"  행{XL(i)} {df.buyer_id[i]} max_dpd={d} 인데 더 오래된 구간 잔액 있음: {over}")

print("\n## 재무 항목")
F = df[FIN].apply(pd.to_numeric, errors="coerce")
for c in FIN:
    print(f"{c}: 결측={F[c].isna().sum()} min={F[c].min():,.0f} max={F[c].max():,.0f} 음수={(F[c] < 0).sum()} 0={(F[c] == 0).sum()}")
crc = pd.to_numeric(df.oecd_crc, errors="coerce")
miss = F.isna().any(axis=1)
print("재무 결측 1개 이상 바이어 수:", int(miss.sum()))
print("CRC≥3 중 결측률:", round(miss[crc >= 3].mean(), 3), "| CRC<3 또는 미분류 중 결측률:", round(miss[~(crc >= 3)].mean(), 3))
print("equity<=0:", [(XL(i), df.buyer_id[i], F.equity[i]) for i in F.index[F.equity <= 0]])
print("total_liabilities < current_liabilities:", df.buyer_id[F.total_liabilities < F.current_liabilities].tolist())
print("accounts_receivable > current_assets:", df.buyer_id[F.accounts_receivable > F.current_assets].tolist())
print("|operating_income| > revenue:", df.buyer_id[F.operating_income.abs() > F.revenue].tolist())
print("revenue<=0:", df.buyer_id[F.revenue <= 0].tolist())
