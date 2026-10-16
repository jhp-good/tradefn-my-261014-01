"""3일차 실습 C — 한빛식당(가상) 점심 기록 정제. 원본은 읽기만 한다.

실행: uv run python scripts/lunch_clean.py
규칙: workbench/day3/outputs/lunch_rules.md 의 표 그대로, 그 순서로 적용
      (R1 → R2 → R3 → R4 → R5 → R10 → R6 → R7 → R8 → R9)
결과: workbench/day3/outputs/lunch_clean.csv (UTF-8 BOM, 원본과 같은 10개 열)
      workbench/day3/outputs/lunch_clean_log.md (규칙별 고친 · 뺀 줄 수)
"""
import csv
import datetime as dt
import math
import pathlib
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")

SRC = pathlib.Path("labs/day3/lab-c/hanbit_lunch_log.csv")
OUT_CSV = pathlib.Path("workbench/day3/outputs/lunch_clean.csv")
OUT_LOG = pathlib.Path("workbench/day3/outputs/lunch_clean_log.md")

# 수강생 결정(프롬프트): "'수기 집계' 줄은 뺀다" → "drop" / "×10 보정"이면 "x10"
HANDWRITTEN_DECISION = "drop"

WEEKDAYS = "월화수목금토일"  # date.weekday() 0=월
WEEKDAY_EN = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
WEATHER_MAP = {
    "맑음": "맑음", "맑": "맑음", "sunny": "맑음",
    "흐림": "흐림", "구름많음": "흐림", "cloudy": "흐림",
    "비": "비", "rain": "비", "우천": "비", "소나기": "비", "흐리고 비": "비",
    "눈": "눈", "snow": "눈",
    "": "모름",
}
MENU_MAP = {"돈까스": "돈가스", "카레라이스": "카레", "제육": "제육볶음", "치킨마요덮밥": "치킨마요", "김치 찌개": "김치찌개"}
EVENT_MAP = {"외부손님": "외부 손님 방문", "전사교육": "전사 교육"}
LOW_RATIO = 0.2


def round_half_up(x):
    return math.floor(x + 0.5)


def parse_date(s):
    """R1: 네 형식을 date로. 연도가 없으면 10–12월 → 2025, 1–9월 → 2026."""
    s = s.strip()
    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s):
        return dt.date(*map(int, m.groups()))
    if m := re.fullmatch(r"(\d{1,2})월 (\d{1,2})일", s):
        mo, d = map(int, m.groups())
        return dt.date(2025 if mo >= 10 else 2026, mo, d)
    raise ValueError(f"해석할 수 없는 날짜: {s!r}")


def norm_weekday(s):
    s = s.strip()
    if s in WEEKDAY_EN:
        return WEEKDAY_EN[s]
    return s[:-2] if s.endswith("요일") else s


# ---------- 읽기 ----------
with SRC.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    COLUMNS = reader.fieldnames
    rows = [dict(r, _line=i + 2) for i, r in enumerate(reader)]  # _line: 원본 CSV 줄 번호

n_start = len(rows)
log = []  # (순서, 규칙, 할 일, 고친(뺀) 줄 수, 남은 줄 수)
details = {}  # 규칙 → 자세한 줄 목록(보고서용)


def record(order, rule, what, n_changed):
    log.append((order, rule, what, n_changed, len(rows)))
    print(f"{order:>2} {rule:<3} {what}: {n_changed} → 남은 줄 {len(rows)}")


# 1 R1 날짜를 YYYY-MM-DD로
n = 0
for r in rows:
    r["_date"] = parse_date(r["날짜"])
    iso = r["_date"].isoformat()
    if r["날짜"] != iso:
        n += 1
    r["날짜"] = iso
record(1, "R1", "날짜 형식을 YYYY-MM-DD로 바꾼 줄", n)

# 2 R2 요일을 날짜에서 다시 계산 — 적힌 요일이 실제와 '달랐던' 줄만 센다
wrong = []
for r in rows:
    actual = WEEKDAYS[r["_date"].weekday()]
    if norm_weekday(r["요일"]) != actual:
        wrong.append((r["_line"], r["날짜"], r["요일"], actual))
    r["요일"] = actual
details["R2"] = wrong
record(2, "R2", "적힌 요일이 실제 요일과 달랐던 줄", len(wrong))

# 3 R3 휴무 줄 빼기
before = len(rows)
rows = [r for r in rows if r["비고"] != "휴무"]
record(3, "R3", "비고 '휴무' 줄을 뺌", before - len(rows))

# 4 R4 같은 날짜 두 줄 → '재집계' 줄, 없으면 나중 줄
keep = {}
for r in rows:  # 파일 순서대로 → 나중 줄이 덮어씀
    d = r["날짜"]
    if d in keep and "재집계" in keep[d]["비고"] and "재집계" not in r["비고"]:
        continue
    keep[d] = r
kept_ids = {id(r) for r in keep.values()}
dropped = [r for r in rows if id(r) not in kept_ids]
details["R4"] = [(r["_line"], r["날짜"], r["식수"], r["비고"]) for r in dropped]
rows = [r for r in rows if id(r) in kept_ids]
record(4, "R4", "같은 날짜의 남는 줄을 뺌", len(dropped))

# 5 R5 식수 빈칸 빼기
before = len(rows)
details["R5"] = [(r["_line"], r["날짜"], r["비고"]) for r in rows if not r["식수"].strip()]
rows = [r for r in rows if r["식수"].strip()]
record(5, "R5", "식수 빈칸 줄을 뺌", before - len(rows))

# 6 R10 출근예정 빈칸 → 같은 요일 바로 앞 기록 4개(출근예정 있는 줄)의 median, 반올림
rows.sort(key=lambda r: r["_date"])  # 날짜순(같은 날짜는 이미 하나뿐)
filled = []
for r in rows:
    if r["출근예정"].strip():
        continue
    prev = [p for p in rows
            if p["_date"] < r["_date"] and p["요일"] == r["요일"] and p["출근예정"].strip() and "_filled" not in p]
    last4 = prev[-4:]
    if len(last4) < 4:
        print(f"  주의: 줄 {r['_line']} {r['날짜']} 앞 같은 요일 기록이 {len(last4)}개뿐 — 확인 필요")
    vals = [int(p["출근예정"]) for p in last4]
    med = statistics.median(vals)
    r["출근예정"] = str(round_half_up(med))
    r["_filled"] = True
    filled.append((r["_line"], r["날짜"], r["요일"], [p["날짜"] for p in last4], vals, med, r["출근예정"]))
details["R10"] = filled
record(6, "R10", "출근예정 빈칸을 채운 줄", len(filled))

# 7 R6 불가능한 식수 빼기 + '수기 집계' 줄은 수강생 결정대로
removed, fixed = [], []
out = []
for r in rows:
    meal, plan = int(r["식수"]), int(r["출근예정"])
    if r["비고"] == "수기 집계":
        if HANDWRITTEN_DECISION == "drop":
            removed.append((r["_line"], r["날짜"], plan, meal, r["비고"], "수강생 결정: 뺀다"))
            continue
        r["식수"] = str(meal * 10)
        fixed.append((r["_line"], r["날짜"], plan, meal, r["비고"], "수강생 결정: ×10 보정"))
        out.append(r)
        continue
    if meal > plan:
        removed.append((r["_line"], r["날짜"], plan, meal, r["비고"], "식수 > 출근예정"))
    elif meal < LOW_RATIO * plan:
        removed.append((r["_line"], r["날짜"], plan, meal, r["비고"], "식수 < 출근예정의 20%"))
    else:
        out.append(r)
rows = out
details["R6"] = removed + fixed
record(7, "R6", "불가능한 식수 줄을 뺌(·'수기 집계' 결정 반영)", len(removed) + len(fixed))

# 8 R7 날씨 넷으로(빈칸 → 모름)
n = 0
for r in rows:
    raw = r["날씨"].strip()
    if raw not in WEATHER_MAP:
        raise ValueError(f"규칙에 없는 날씨 표기: {raw!r} (줄 {r['_line']}) — 확인 필요")
    if WEATHER_MAP[raw] != r["날씨"]:
        n += 1
    r["날씨"] = WEATHER_MAP[raw]
record(8, "R7", "날씨 표기를 바꾼 줄(빈칸 → 모름 포함)", n)

# 9 R8 최고기온 단위 · 공백 떼기
n = 0
for r in rows:
    t = r["최고기온"].replace("℃", "").replace("°C", "").replace(" ", "").strip()
    if t and not re.fullmatch(r"-?\d+(\.\d+)?", t):
        raise ValueError(f"숫자가 아닌 최고기온: {r['최고기온']!r} (줄 {r['_line']}) — 확인 필요")
    if t != r["최고기온"]:
        n += 1
    r["최고기온"] = t
record(9, "R8", "최고기온에서 단위 · 공백을 뗀 줄", n)

# 10 R9 이름 통일 — 메뉴와 행사를 따로 세어 더한다
n_menu = n_event = 0
for r in rows:
    if r["메인메뉴"] in MENU_MAP:
        r["메인메뉴"] = MENU_MAP[r["메인메뉴"]]
        n_menu += 1
    if r["행사"] in EVENT_MAP:
        r["행사"] = EVENT_MAP[r["행사"]]
        n_event += 1
details["R9"] = (n_menu, n_event)
record(10, "R9", f"이름을 통일한 칸(메뉴 {n_menu} + 행사 {n_event})", n_menu + n_event)

# ---------- 마지막 정리 · 저장 ----------
for r in rows:
    r["월급날"] = "1" if r["월급날"].strip() == "Y" else "0"
    r["출근예정"] = str(int(r["출근예정"]))
    r["식수"] = str(int(r["식수"]))
rows.sort(key=lambda r: r["_date"])
assert len({r["날짜"] for r in rows}) == len(rows), "같은 날짜가 남아 있음"

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

# ---------- 로그 ----------
L = ["# 한빛식당(가상) 점심 기록 — 정제 로그\n"]
L.append(f"- 원본: `{SRC.as_posix()}` · 규칙: `workbench/day3/outputs/lunch_rules.md` · 코드: `scripts/lunch_clean.py`")
L.append(f"- 처음 {n_start}줄 → 남은 {len(rows)}줄 · 결과: `{OUT_CSV.as_posix()}`")
L.append(f"- 날짜 범위: {rows[0]['날짜']} ~ {rows[-1]['날짜']}")
L.append("- 세는 법: 그 규칙을 적용할 때 남아 있는 줄에서 센다. R2는 적힌 요일이 실제 요일과 달랐던 줄만, "
         "R9는 메뉴와 행사를 따로 세어 더한다.\n")
L.append("| 순서 | 규칙 | 한 일 | 고친(뺀) 줄 수 | 남은 줄 수 |\n|---:|---|---|---:|---:|")
for order, rule, what, nch, left in log:
    L.append(f"| {order} | {rule} | {what} | {nch} | {left} |")
L.append("")

L.append("## 자세히\n")
L.append("### R2 — 적힌 요일이 실제와 달랐던 줄\n")
L.append("| 원본 줄 | 날짜 | 적힌 요일 | 실제 요일 |\n|---:|---|---|---|")
L += [f"| {a} | {b} | `{c}` | {d} |" for a, b, c, d in details["R2"]]
L.append("\n### R4 — 같은 날짜에서 뺀 줄\n")
L.append("| 원본 줄 | 날짜 | 식수 | 비고 |\n|---:|---|---:|---|")
L += [f"| {a} | {b} | {c} | {d or '(빈칸)'} |" for a, b, c, d in details["R4"]]
L.append("\n### R5 — 식수 빈칸으로 뺀 줄\n")
L.append("| 원본 줄 | 날짜 | 비고 |\n|---:|---|---|")
L += [f"| {a} | {b} | {c} |" for a, b, c in details["R5"]]
L.append("\n### R10 — 출근예정을 채운 줄\n")
L.append("| 원본 줄 | 날짜 | 요일 | 앞 같은 요일 4개(날짜) | 그 출근예정 | 가운데 값 | 채운 값 |\n|---:|---|---|---|---|---:|---:|")
L += [f"| {a} | {b} | {c} | {', '.join(d)} | {', '.join(map(str, e))} | {m} | {v} |"
      for a, b, c, d, e, m, v in details["R10"]]
L.append("\n### R6 — 뺀(고친) 줄\n")
L.append("| 원본 줄 | 날짜 | 출근예정 | 식수 | 비고 | 이유 |\n|---:|---|---:|---:|---|---|")
L += [f"| {a} | {b} | {c} | {d} | {e or '(빈칸)'} | {g} |" for a, b, c, d, e, g in details["R6"]]
L.append(f"\n'수기 집계' 줄: 수강생 결정 **{'뺀다' if HANDWRITTEN_DECISION == 'drop' else '×10 보정'}** 대로 처리.")
OUT_LOG.write_text("\n".join(L) + "\n", encoding="utf-8")

print(f"처음 {n_start}줄 → 남은 {len(rows)}줄 · {rows[0]['날짜']} ~ {rows[-1]['날짜']}")
print("R6 상세:", details["R6"])
print("R10 상세:", details["R10"])
print(f"저장: {OUT_CSV.as_posix()} · {OUT_LOG.as_posix()}")
