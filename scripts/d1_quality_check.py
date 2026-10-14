"""1일차 바이어 원본(d1_buyers_raw.xlsx) 품질 진단 — 읽기만 하고 고치지 않는다.

실행: uv run python scripts/d1_quality_check.py
결과는 화면에 출력만 한다. 보고서(workbench/day1/outputs/d1_quality_report.md)는 이 출력을 보고 쓴다.
"""
import collections
import datetime as dt
import re

import openpyxl

SRC = "data/day1/d1_buyers_raw.xlsx"
DICT = "data/data_dictionary.xlsx"
REF_DATE = dt.date(2026, 9, 30)  # readme 시트의 기준일

# 데이터 사전(columns 시트)에서 dtype이 number · integer · number/text 인 열
NUMERIC_COLS = [
    "ar_balance", "max_dpd_days", "overdue_amount", "pay_score", "oecd_crc",
    "revenue_usd_fy2025", "current_ratio_fy2025", "debt_to_equity_fy2025",
    "dso_fy2025", "op_margin_fy2025",
]

# 날짜 표기 패턴 — 이름: 정규식
DATE_PATTERNS = {
    "YYYY-MM-DD": r"^\d{4}-\d{2}-\d{2}$",
    "YYYY.M.D": r"^\d{4}\.\d{1,2}\.\d{1,2}$",
    "DD/MM/YYYY 또는 MM/DD/YYYY": r"^\d{2}/\d{2}/\d{4}$",
    "Mon D YYYY": r"^[A-Z][a-z]{2} \d{1,2} \d{4}$",
}


def is_blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def looks_numeric_text(s):
    """글자인데 숫자로 읽힐 만한 값(쉼표 · 통화 · k · 한글 수량어 · 단위가 붙은 숫자)."""
    return isinstance(s, str) and bool(re.search(r"\d", s))


def section(title):
    print(f"\n{'=' * 10} {title} {'=' * 10}")


wb = openpyxl.load_workbook(SRC)  # 값만 읽는다. 저장하지 않는다
ws = wb["buyers"]
rows = list(ws.iter_rows(values_only=True))
hdr, data = list(rows[0]), [list(r) for r in rows[1:]]
col = {h: [r[j] for r in data] for j, h in enumerate(hdr)}
ids = col["buyer_id"]
print(f"시트 buyers: 데이터 {len(data)}행 × {len(hdr)}열")

# ---------- 1) 열별 유형 · 결측 ----------
section("열별 파이썬 유형 · 결측(빈칸 · 공백만) · 앞뒤 공백")
for h in hdr:
    vals = col[h]
    types = collections.Counter(type(v).__name__ for v in vals if not is_blank(v))
    blanks = sum(is_blank(v) for v in vals)
    ws_pad = [v for v in vals if isinstance(v, str) and v != v.strip()]
    print(f"{h:24s} 유형={dict(types)} 결측={blanks} 앞뒤공백={len(ws_pad)} 고유값={len(set(map(repr, vals)))}")

# ---------- 2) 중복 ----------
section("중복")
full = collections.Counter(tuple(map(repr, r)) for r in data)
print("완전 중복 행 묶음:", [(k[0], n) for k, n in full.items() if n > 1])
dup_ids = [k for k, n in collections.Counter(ids).items() if n > 1]
for k in dup_ids:
    idx = [i for i, v in enumerate(ids) if v == k]
    same = all(data[i] == data[idx[0]] for i in idx)
    print(f"buyer_id {k}: 엑셀 행 {[i + 2 for i in idx]} · 모든 열 동일={same}")
norm_name = collections.defaultdict(set)
for i, n in enumerate(col["buyer_name"]):
    norm_name[re.sub(r"\W+", "", str(n)).lower()].add(ids[i])
print("이름(공백 · 기호 · 대소문자 무시)이 같은데 ID가 다른 묶음:",
      [sorted(v) for v in norm_name.values() if len(v) > 1])
print("고유 buyer_id 수:", len(set(ids)))

# ---------- 3) 숫자 열에 들어간 글자 ----------
section("숫자 열의 글자 값")
for h in NUMERIC_COLS:
    txt = [(ids[i], v) for i, v in enumerate(col[h]) if isinstance(v, str)]
    print(f"{h}: {len(txt)}건 {txt}")
section("숫자 열의 소수(정수여야 하는 금액 · 일수)")
for h in ["ar_balance", "overdue_amount", "max_dpd_days", "pay_score"]:
    print(h, [(ids[i], v) for i, v in enumerate(col[h]) if isinstance(v, float)])

# ---------- 4) 날짜 형식 ----------
section("since_date 형식")
fmt_count, fmt_ex, ambiguous, other = collections.Counter(), collections.defaultdict(list), [], []
for i, v in enumerate(col["since_date"]):
    s = v if isinstance(v, str) else repr(v)
    name = next((k for k, p in DATE_PATTERNS.items() if re.match(p, s)), None)
    if name is None:
        other.append((ids[i], s))
        continue
    fmt_count[name] += 1
    fmt_ex[name].append(s)
    if name.startswith("DD/MM"):
        a, b, _ = map(int, s.split("/"))
        if a <= 12 and b <= 12:
            ambiguous.append((ids[i], s))
print("셀 유형:", collections.Counter(type(v).__name__ for v in col["since_date"]))
for k, n in fmt_count.items():
    print(f"{k}: {n}건 예 {fmt_ex[k][:3]}")
print("어느 패턴에도 안 맞음:", other)
print("슬래시 표기 중 일·월 둘 다 12 이하(뜻이 두 가지):", len(ambiguous), ambiguous)
slash_first_gt12 = [s for s in fmt_ex.get("DD/MM/YYYY 또는 MM/DD/YYYY", []) if int(s[:2]) > 12]
slash_second_gt12 = [s for s in fmt_ex.get("DD/MM/YYYY 또는 MM/DD/YYYY", []) if int(s[3:5]) > 12]
print("앞자리 > 12 (DD/MM 근거):", slash_first_gt12[:5], len(slash_first_gt12))
print("가운데 > 12 (MM/DD 근거):", slash_second_gt12[:5], len(slash_second_gt12))


def parse_unambiguous(s):
    for f in ("%Y-%m-%d", "%Y.%m.%d", "%b %d %Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


after_ref = [(ids[i], v) for i, v in enumerate(col["since_date"])
             if (d := parse_unambiguous(v)) and d > REF_DATE]
print(f"기준일 {REF_DATE} 이후 날짜(슬래시는 DD/MM로 가정):", after_ref)

# ---------- 5) 범주 · 표기 흔들림 ----------
section("범주 열 값 분포")
for h in ["country", "country_code", "region", "industry", "segment", "buyer_type",
          "ar_currency", "ksure_insured", "oecd_crc"]:
    print(h, dict(collections.Counter(map(repr, col[h])).most_common()))

section("country ↔ country_code 대응")
pairs = collections.Counter(zip(col["country"], col["country_code"]))
for (c, cc), n in sorted(pairs.items(), key=lambda x: x[0][1]):
    print(f"{cc} ← {c!r} ({n})")
code_region = collections.defaultdict(set)
for cc, rg in zip(col["country_code"], col["region"]):
    code_region[cc].add(rg)
print("코드 하나에 권역이 둘 이상:", {k: v for k, v in code_region.items() if len(v) > 1})
code_crc = collections.defaultdict(set)
for cc, c in zip(col["country_code"], col["oecd_crc"]):
    code_crc[cc].add(c)
print("코드별 oecd_crc:", dict(code_crc))

section("segment · buyer_type · industry 정합")
combo = collections.Counter(zip(col["segment"], col["buyer_type"], col["industry"]))
for k, n in combo.most_common():
    print(k, n)
print("industry 빈칸 행:", [(ids[i], col["segment"][i], col["buyer_type"][i])
                          for i, v in enumerate(col["industry"]) if v is None])

section("payment_terms_raw — 표기 수 · 코드표 대조")
dwb = openpyxl.load_workbook(DICT, read_only=True)
tmap = {r[1]: r[2] for r in dwb["payment_terms_map"].iter_rows(min_row=4, values_only=True) if r[1]}
pt = col["payment_terms_raw"]
print("고유 표기 수:", len(set(pt)), "· TRIM · UPPER 후:", len({p.strip().upper() for p in pt}))
print("앞뒤 공백 표기:", sorted({repr(p) for p in pt if p != p.strip()}))
print("코드표에 없는 표기:", sorted({p for p in pt if p.strip().upper() not in tmap}))
print("표준 코드별 건수:", dict(collections.Counter(tmap.get(p.strip().upper(), "미등록") for p in pt)))
print("한글 표기:", sorted({p for p in pt if re.search(r"[가-힣]", p)}))

# ---------- 6) 값 범위 · 열 사이 논리 ----------
section("값 범위 · 논리 점검")


def num(v):
    return v if isinstance(v, (int, float)) else None


ar, od, dpd = col["ar_balance"], col["overdue_amount"], col["max_dpd_days"]
print("overdue > ar_balance (둘 다 숫자):",
      [(ids[i], ar[i], od[i]) for i in range(len(data))
       if num(ar[i]) is not None and num(od[i]) is not None and od[i] > ar[i]])
print("dpd > 0 인데 overdue = 0:",
      [(ids[i], dpd[i], od[i]) for i in range(len(data)) if num(dpd[i]) and num(dpd[i]) > 0 and od[i] == 0])
print("dpd = 0 인데 overdue > 0:",
      [(ids[i], dpd[i], od[i]) for i in range(len(data)) if dpd[i] == 0 and num(od[i]) and od[i] > 0])
print("ar_balance 빈칸 행:", [(ids[i], col['ar_currency'][i]) for i, v in enumerate(ar) if v is None])
print("pay_score 1~100 밖:", [(ids[i], v) for i, v in enumerate(col["pay_score"]) if num(v) is not None and not 1 <= v <= 100])
print("pay_score 하위 5:", sorted([(v, ids[i]) for i, v in enumerate(col["pay_score"]) if num(v) is not None])[:5])
print("max_dpd_days 91 이상(숫자):", [(ids[i], v) for i, v in enumerate(dpd) if num(v) and v >= 91])
big = sorted([(v, ids[i], col["ar_currency"][i]) for i, v in enumerate(ar) if num(v)], reverse=True)[:8]
print("ar_balance 상위 8 (값, ID, 통화):", big)
print("debt_to_equity 음수(사전상 자본잠식):", [(ids[i], v) for i, v in enumerate(col["debt_to_equity_fy2025"]) if num(v) is not None and v < 0])
print("current_ratio < 1:", sum(1 for v in col["current_ratio_fy2025"] if num(v) is not None and v < 1))
for h in ["current_ratio_fy2025", "debt_to_equity_fy2025", "dso_fy2025", "op_margin_fy2025", "revenue_usd_fy2025"]:
    xs = [v for v in col[h] if num(v) is not None]
    print(f"{h}: 최소 {min(xs)} · 최대 {max(xs)}")

section("fin_summary_text ↔ 숫자 열 대조")
mism, notdisc = [], 0
for i, t in enumerate(col["fin_summary_text"]):
    if "not disclosed" in t:
        notdisc += 1
    m_rev = re.search(r"USD ([\d.]+)M", t)
    m_mg = re.search(r"(-?[\d.]+)% margin|operating margin (-?[\d.]+)%", t)
    rev = col["revenue_usd_fy2025"][i]
    mg = col["op_margin_fy2025"][i]
    if m_rev and num(rev) is not None and abs(float(m_rev.group(1)) - rev / 1e6) > 0.05 + 1e-9:
        mism.append((ids[i], "매출", m_rev.group(1), rev))
    if m_mg and num(mg) is not None:
        txt = float(m_mg.group(1) or m_mg.group(2))
        if abs(txt - mg * 100) > 0.05 + 1e-9:
            mism.append((ids[i], "영업이익률", txt, mg))
print("문장과 숫자 열이 다른 행:", mism)
print("'not disclosed' 문장 수:", notdisc)
no_rev = [ids[i] for i, v in enumerate(col["revenue_usd_fy2025"]) if v is None]
print("revenue 빈칸 행의 문장 예:", [(k, col["fin_summary_text"][ids.index(k)]) for k in no_rev[:3]])
