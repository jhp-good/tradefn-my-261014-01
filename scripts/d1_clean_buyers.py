"""1일차 분석용 바이어 표 — 원본을 읽어 메모리에서만 정리한다(파일로 저장하지 않는다).

근거: workbench/day1/outputs/d1_quality_report.md (진단) · d1_code_table.csv (결제조건 코드표)
사용: from d1_clean_buyers import load_clean_buyers  →  df = load_clean_buyers()
원본 열은 그대로 두고, 정리한 값은 새 열로 더한다.

정리 규칙
  R1 중복      buyer_id 기준 첫 행만 남긴다(B047 완전 중복 · B094 · B114 이름 표기만 다름) → 150행
  R2 결제조건  payment_terms_raw를 TRIM · UPPER 한 뒤 코드표에서 찾아 pay_method. 코드표의 '검토 필요'는 그대로 둔다
  R3 연체일수  숫자는 그대로, '90일' · '381 days'처럼 숫자 + 단위는 숫자만, '확인중' · '-'는 빈칸(모름)
  R4 연체 여부 is_overdue = dpd > 0. dpd가 빈칸이면 빈칸(모름) — 비율의 분모에서 뺀다
  R5 금액      쉼표 · 'USD ' 접두 제거, 'k' = ×1,000, '약 11만9천' 같은 한글 수량어 환산. '약'이 붙으면 amount_approx=True
  R6 통화      usd · US$ → USD, € → EUR. '¥'는 JPY · CNY 둘 다 가능해 빈칸(확인 필요)
  R7 국가명    country_code(ISO alpha-3, 오타 없음)에서 다시 만든다
  R8 거래시작일 4가지 형식을 각각 읽는다. 슬래시는 DD/MM으로 읽고(진단: 앞자리>12가 18건, 가운데>12가 0건)
               일 · 월 모두 12 이하면 since_date_ambiguous=True
  R9 OECD 등급 '-'(분류 대상 아님)는 0이 아니므로 숫자 열은 빈칸, crc_not_classified=True
  R10 업종     빈칸은 'unknown'
  R11 부채비율 음수는 지우지 않고 capital_impaired=True(사전: 음수 = 자본잠식)
"""
import re
from pathlib import Path

import pandas as pd

RAW = Path("data/day1/d1_buyers_raw.xlsx")
CODE_TABLE = Path("workbench/day1/outputs/d1_code_table.csv")

COUNTRY_NAME = {  # ISO alpha-3 → 국가명(한글)
    "USA": "미국", "CHN": "중국", "VNM": "베트남", "DEU": "독일", "JPN": "일본",
    "IND": "인도", "IDN": "인도네시아", "TUR": "튀르키예", "MEX": "멕시코", "ARE": "아랍에미리트",
    "POL": "폴란드", "GBR": "영국", "NLD": "네덜란드", "TWN": "대만", "SAU": "사우디아라비아",
    "THA": "태국", "EGY": "이집트", "MYS": "말레이시아", "BRA": "브라질", "NGA": "나이지리아",
}
CURRENCY = {"USD": "USD", "US$": "USD", "EUR": "EUR", "€": "EUR", "JPY": "JPY", "CNY": "CNY"}


def parse_amount(v):
    """(숫자, 근사 여부) — 숫자로 못 읽으면 (None, False)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, False
    if isinstance(v, (int, float)):
        return float(v), False
    s = str(v).strip()
    approx = s.startswith("약")
    s = s.removeprefix("약").strip().removeprefix("USD").strip().replace(",", "")
    if m := re.fullmatch(r"([\d.]+)k", s, re.I):
        return float(m.group(1)) * 1_000, approx
    if m := re.fullmatch(r"(?:(\d+)만)?\s*(?:(\d+)천)?", s):
        if m.group(1) or m.group(2):
            return int(m.group(1) or 0) * 10_000 + int(m.group(2) or 0) * 1_000, approx
    try:
        return float(s), approx
    except ValueError:
        return None, False


def parse_dpd(v):
    if isinstance(v, (int, float)) and not pd.isna(v):
        return float(v)
    m = re.fullmatch(r"\s*(\d+)\s*(일|days?)?\s*", str(v))
    return float(m.group(1)) if m else None


def parse_since(s):
    """(날짜, 일·월이 모호한지)"""
    s = str(s).strip()
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        d, m, _ = map(int, s.split("/"))
        return pd.to_datetime(s, format="%d/%m/%Y"), d <= 12 and m <= 12
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%b %d %Y"):
        try:
            return pd.to_datetime(s, format=fmt), False
        except ValueError:
            pass
    return pd.NaT, False


def load_code_map(path=CODE_TABLE):
    ct = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    ct["key"] = ct["원래 표기"].str.strip().str.upper()
    conflict = ct.groupby("key")["표준 코드"].nunique()
    if (conflict > 1).any():
        raise ValueError(f"같은 표기에 코드가 둘 이상: {list(conflict[conflict > 1].index)}")
    return dict(zip(ct["key"], ct["표준 코드"]))


def load_clean_buyers(raw=RAW, code_table=CODE_TABLE):
    df = pd.read_excel(raw, sheet_name="buyers", dtype=object)  # 섞인 유형을 그대로 받는다
    n_raw = len(df)

    df = df.drop_duplicates(subset="buyer_id", keep="first").reset_index(drop=True)  # R1
    df.attrs["n_raw_rows"], df.attrs["n_dropped_dup"] = n_raw, n_raw - len(df)

    code_map = load_code_map(code_table)  # R2
    key = df["payment_terms_raw"].str.strip().str.upper()
    unmapped = sorted(set(key) - code_map.keys())
    if unmapped:
        raise ValueError(f"코드표에 없는 결제조건: {unmapped}")
    df["pay_method"] = key.map(code_map)

    df["dpd"] = df["max_dpd_days"].map(parse_dpd).astype("Float64")  # R3
    df["is_overdue"] = (df["dpd"] > 0).astype("boolean")  # R4 — dpd가 빈칸이면 빈칸

    for c in ["ar_balance", "overdue_amount"]:  # R5
        parsed = df[c].map(parse_amount)
        df[f"{c}_num"] = parsed.map(lambda t: t[0]).astype("Float64")
        df[f"{c}_approx"] = parsed.map(lambda t: t[1])
    df["amount_approx"] = df["ar_balance_approx"] | df["overdue_amount_approx"]
    df = df.drop(columns=["ar_balance_approx", "overdue_amount_approx"])

    df["currency"] = df["ar_currency"].str.strip().str.upper().map(CURRENCY)  # R6 — '¥'는 표에 없어 빈칸
    df["country_std"] = df["country_code"].map(COUNTRY_NAME)  # R7

    since = df["since_date"].map(parse_since)  # R8
    df["since"] = pd.to_datetime(since.map(lambda t: t[0]))
    df["since_date_ambiguous"] = since.map(lambda t: t[1])

    df["crc_not_classified"] = df["oecd_crc"].eq("-")  # R9
    df["oecd_crc_num"] = pd.to_numeric(df["oecd_crc"].where(~df["crc_not_classified"]), errors="coerce").astype("Float64")

    df["industry_std"] = df["industry"].fillna("unknown")  # R10
    for c in ["pay_score", "revenue_usd_fy2025", "current_ratio_fy2025",
              "debt_to_equity_fy2025", "dso_fy2025", "op_margin_fy2025"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Float64")
    df["capital_impaired"] = (df["debt_to_equity_fy2025"] < 0).fillna(False).astype(bool)  # R11
    return df


def overdue_rate(df, by):
    """그룹별 바이어 수 · dpd 모름 · 연체 바이어 수 · 연체 비율(분모 = dpd를 아는 바이어)."""
    g = df.groupby(by, dropna=False)
    out = pd.DataFrame({
        "바이어 수": g.size(),
        "dpd 모름": g["dpd"].apply(lambda s: int(s.isna().sum())),
        "연체 바이어 수": g["is_overdue"].apply(lambda s: int(s.fillna(False).sum())),
    })
    out["분모(dpd 확인)"] = out["바이어 수"] - out["dpd 모름"]
    out["연체 비율"] = out["연체 바이어 수"] / out["분모(dpd 확인)"]
    return out
