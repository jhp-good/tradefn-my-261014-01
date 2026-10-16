"""3일차 실습 C — 한빛식당(가상) 점심 기록(hanbit_lunch_log.csv) 품질 진단. 읽기만 하고 고치지 않는다.

실행: uv run python scripts/lunch_quality.py
결과: workbench/day3/outputs/lunch_quality.md (보고서의 숫자는 모두 이 스크립트가 센 값)
기준: labs/day3/lab-c/lab_c_guide.md 「3. 데이터 진단」
"""
import collections
import csv
import datetime as dt
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

SRC = pathlib.Path("labs/day3/lab-c/hanbit_lunch_log.csv")
OUT = pathlib.Path("workbench/day3/outputs/lunch_quality.md")

WEEKDAYS = "월화수목금토일"  # date.weekday() 0=월
WEEKDAY_EN = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
WEATHER_STD = {"맑음", "흐림", "비", "눈"}
LOW_RATIO = 0.2  # 안내서 R6의 선: 출근예정의 20% 미만이면 너무 적음
# 안내서 R9의 이름 통일 목록에 나오는 '흔들린 이름'
MENU_VARIANTS = {"돈까스", "카레라이스", "제육", "치킨마요덮밥", "김치 찌개"}
EVENT_VARIANTS = {"외부손님", "전사교육"}

# 날짜 형식 — 이름: 정규식
DATE_FORMATS = {
    "YYYY-MM-DD": r"^(\d{4})-(\d{2})-(\d{2})$",
    "YYYY/MM/DD": r"^(\d{4})/(\d{1,2})/(\d{1,2})$",
    "YYYY.M.D": r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$",
    "M월 D일(연도 없음)": r"^(\d{1,2})월 (\d{1,2})일$",
}


def date_format(s):
    return next((k for k, p in DATE_FORMATS.items() if re.match(p, s)), None)


def parse_date(s):
    """진단용 해석. 연도가 없으면 안내서 R1 규칙(10–12월 → 2025, 1–9월 → 2026)."""
    fmt = date_format(s)
    if fmt is None:
        return None
    g = list(map(int, re.match(DATE_FORMATS[fmt], s).groups()))
    if fmt.startswith("M월"):
        m, d = g
        return dt.date(2025 if m >= 10 else 2026, m, d)
    return dt.date(*g)


def norm_weekday(s):
    s = s.strip()
    if s in WEEKDAY_EN:
        return WEEKDAY_EN[s]
    if s.endswith("요일"):
        s = s[:-2]
    return s if len(s) == 1 and s in WEEKDAYS else None


def to_int(s):
    return int(s) if re.fullmatch(r"-?\d+", s.strip()) else None


def ex(r, text):
    """예시 칸: 원본 글자 그대로 + CSV 줄 번호."""
    return f"`{text}` (줄 {r['_line']})"


# ---------- 읽기 ----------
with SRC.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    columns = reader.fieldnames
    rows = []
    for i, r in enumerate(reader):
        r["_line"] = i + 2  # 머리줄이 1줄
        r["_date"] = parse_date(r["날짜"])
        rows.append(r)

n_rows = len(rows)
dates = [r["_date"] for r in rows if r["_date"]]
unparsed = [r for r in rows if r["_date"] is None]
holiday = [r for r in rows if r["비고"] == "휴무"]
work = [r for r in rows if r["비고"] != "휴무"]  # 휴무 줄을 뺀 나머지

# ---------- 종류별 ----------
kinds = []  # (종류, 줄 수, [예시 행, 글자], 내역)

# 1 날짜 형식 섞임
fmt_count = collections.Counter(date_format(r["날짜"]) or "알 수 없음" for r in rows)
bad_date = [r for r in rows if date_format(r["날짜"]) != "YYYY-MM-DD"]
kinds.append(("날짜 형식 섞임", len(bad_date), [ex(r, r["날짜"]) for r in bad_date],
              " · ".join(f"{k} {v}" for k, v in fmt_count.most_common())))

# 2 요일 표기 섞임
bad_wd = [r for r in rows if r["요일"] not in set("월화수목금")]
wd_count = collections.Counter(r["요일"] for r in bad_wd)
kinds.append(("요일 표기 섞임", len(bad_wd), [ex(r, r["요일"]) for r in bad_wd],
              " · ".join(f"`{k}` {v}" for k, v in wd_count.most_common())))

# 3 같은 날짜가 두 줄
by_date = collections.defaultdict(list)
for r in rows:
    by_date[r["_date"]].append(r)
dup_groups = {d: g for d, g in by_date.items() if d and len(g) > 1}
dup_rows = [r for g in dup_groups.values() for r in g]
fields = [c for c in columns]
identical = [d for d, g in dup_groups.items() if len({tuple(r[c] for c in fields) for r in g}) == 1]
recount = [d for d, g in dup_groups.items() if any("재집계" in r["비고"] for r in g)]
kinds.append(("같은 날짜가 두 줄", len(dup_rows),
              [f"`{d}` ×{len(g)} (줄 {', '.join(str(r['_line']) for r in g)})" for d, g in dup_groups.items()],
              f"날짜 {len(dup_groups)}개 · 모든 열이 똑같은 묶음 {len(identical)} · '재집계' 줄이 있는 묶음 {len(recount)}"))

# 4 휴무 줄
kinds.append(("휴무 줄", len(holiday), [ex(r, ",".join(r[c] for c in columns)) for r in holiday],
              "출근예정 · 식수가 0"))

# 5 식수 빈칸
blank_meal = [r for r in rows if r["식수"].strip() == ""]
kinds.append(("식수 빈칸", len(blank_meal), [ex(r, f"{r['날짜']} · 비고 {r['비고']}") for r in blank_meal],
              " · ".join(f"비고 `{k}` {v}" for k, v in collections.Counter(r["비고"] for r in blank_meal).items())))

# 6 불가능해 보이는 식수
impossible, unjudged = [], []
for r in work:
    meal, plan = to_int(r["식수"]), to_int(r["출근예정"])
    if meal is None:
        continue
    if plan is None:
        unjudged.append(r)
    elif meal > plan or meal < LOW_RATIO * plan:
        impossible.append(r)
over = [r for r in impossible if to_int(r["식수"]) > to_int(r["출근예정"])]
kinds.append(("불가능해 보이는 식수", len(impossible),
              [ex(r, f"출근예정 {r['출근예정']} · 식수 {r['식수']}") for r in impossible],
              f"출근예정보다 많음 {len(over)} · 출근예정의 20% 미만 {len(impossible) - len(over)}"
              f" (출근예정 빈칸이라 판정 못 함 {len(unjudged)})"))

# 7 날씨 표기 섞임 (휴무 제외)
bad_weather = [r for r in work if r["날씨"].strip() and r["날씨"] not in WEATHER_STD]
blank_weather = [r for r in work if not r["날씨"].strip()]
kinds.append(("날씨 표기 섞임", len(bad_weather), [ex(r, r["날씨"]) for r in bad_weather],
              " · ".join(f"`{k}` {v}" for k, v in collections.Counter(r["날씨"] for r in bad_weather).most_common())
              + f" — 이와 따로 빈칸 {len(blank_weather)}줄(휴무 제외)"))

# 8 최고기온 단위와 빈칸 (휴무 제외)
t_c1 = [r for r in work if "℃" in r["최고기온"]]
t_c2 = [r for r in work if "°C" in r["최고기온"]]
t_blank = [r for r in work if not r["최고기온"].strip()]
t_bad = t_c1 + t_c2 + t_blank
kinds.append(("최고기온 단위(℃ · °C)와 빈칸", len(t_bad),
              [ex(t_c1[0], t_c1[0]["최고기온"]), ex(t_c2[0], t_c2[0]["최고기온"])] if t_c1 and t_c2
              else [ex(r, r["최고기온"]) for r in t_bad],
              f"`℃` {len(t_c1)} · `°C` {len(t_c2)} · 빈칸 {len(t_blank)}(휴무 제외)"))

# 9 메뉴 · 행사 이름 섞임
bad_menu = [r for r in rows if r["메인메뉴"] in MENU_VARIANTS]
bad_event = [r for r in rows if r["행사"] in EVENT_VARIANTS]
kinds.append(("메뉴 · 행사 이름 섞임", len(bad_menu) + len(bad_event),
              [ex(bad_menu[0], bad_menu[0]["메인메뉴"]), ex(bad_event[0], bad_event[0]["행사"])],
              "메뉴 " + " · ".join(f"`{k}` {v}" for k, v in collections.Counter(r["메인메뉴"] for r in bad_menu).most_common())
              + f" (계 {len(bad_menu)}) / 행사 "
              + " · ".join(f"`{k}` {v}" for k, v in collections.Counter(r["행사"] for r in bad_event).most_common())
              + f" (계 {len(bad_event)})"))

# 10 출근예정 빈칸 (휴무 제외)
blank_plan = [r for r in work if not r["출근예정"].strip()]
kinds.append(("출근예정 빈칸", len(blank_plan), [ex(r, f"{r['날짜']} · 출근예정 '' · 식수 {r['식수']}") for r in blank_plan],
              "휴무 제외"))

# ---------- 참고: 적힌 요일이 실제 요일과 다른 줄 ----------
wd_wrong = [r for r in rows if r["_date"] and norm_weekday(r["요일"]) != WEEKDAYS[r["_date"].weekday()]]

# ---------- 비고 ----------
memo_count = collections.Counter(r["비고"] for r in rows if r["비고"].strip())

# ---------- 사람이 정할 줄 ----------
decide = {r["_line"]: r for r in impossible + [r for r in rows if r["비고"] == "수기 집계"]}
# 같은 날짜 두 줄인데 값이 다르고 '재집계' 표시도 없는 묶음 — R4가 '나중 줄'로 정하지만 확인할 거리
dup_unclear = [d for d, g in dup_groups.items() if d not in identical and d not in recount]

# ---------- 보고서 ----------
L = []
L.append("# 한빛식당(가상) 점심 기록 — 데이터 진단\n")
L.append(f"- 원본: `{SRC.as_posix()}` (읽기만 함, 고치지 않음)")
L.append("- 세는 코드: `scripts/lunch_quality.py` — 이 보고서의 숫자는 모두 이 스크립트가 센 값")
L.append("- 기준: `labs/day3/lab-c/lab_c_guide.md` 「3. 데이터 진단」")
L.append("- 줄 번호는 CSV 파일의 줄 번호(머리줄 = 1줄)\n")

L.append("## 1. 줄 수 · 열 이름 · 날짜 범위\n")
L.append("| 항목 | 값 |\n|---|---|")
L.append(f"| 데이터 줄 수 | {n_rows}줄 (머리줄 제외) |")
L.append(f"| 열 ({len(columns)}개) | {' · '.join(columns)} |")
L.append(f"| 날짜 범위 | {min(dates)} ~ {max(dates)} |")
L.append(f"| 날짜를 해석하지 못한 줄 | {len(unparsed)}줄 |")
L.append("\n날짜 범위는 네 가지 형식을 해석해 구했다. 연도가 없는 `M월 D일`은 안내서 R1 규칙"
         "(10–12월 → 2025년, 1–9월 → 2026년)으로 읽었다.\n")

L.append("## 2. 엉망인 곳 — 종류별\n")
L.append("| 종류 | 줄 수 | 예시 1 | 예시 2 | 내역 |\n|---|---:|---|---|---|")
for name, cnt, exs, detail in kinds:
    e = (exs + ["—", "—"])[:2]
    L.append(f"| {name} | {cnt} | {e[0]} | {e[1]} | {detail} |")
L.append("\n세는 기준")
L.append("- 날짜 형식 섞임: `YYYY-MM-DD`가 아닌 줄")
L.append("- 요일 표기 섞임: `월`·`화`·`수`·`목`·`금` 한 글자가 아닌 줄(`수요일`, `Mon` 등)")
L.append("- 같은 날짜가 두 줄: 날짜를 해석한 뒤 두 번 이상 나오는 날짜의 줄 전부")
L.append("- 불가능해 보이는 식수: 휴무 · 식수 빈칸 제외, 식수 > 출근예정 또는 식수 < 출근예정 × 0.2(안내서 R6의 선)")
L.append("- 날씨 · 최고기온 · 출근예정: 휴무 줄(값이 모두 비어 있음)은 빼고 셈")
L.append("- 메뉴 · 행사 이름 섞임: 안내서 R9 목록의 이름이 나온 줄. 메뉴와 행사를 따로 세어 더함\n")

L.append("### 참고 — 값별 줄 수\n")
for col in ["날씨", "메인메뉴", "행사"]:
    cnt = collections.Counter(r[col] if r[col].strip() else "(빈칸)" for r in work)
    L.append(f"- **{col}**(휴무 제외): " + " · ".join(f"`{k}` {v}" for k, v in cnt.most_common()))
L.append("")
L.append(f"### 참고 — 적힌 요일이 날짜의 실제 요일과 다른 줄: {len(wd_wrong)}줄\n")
L.append("표기만 다른 줄(`수요일`, `Mon` 등)은 세지 않았다. 정제 R2(요일을 날짜에서 다시 계산)에서 바뀌는 줄이다.\n")
if wd_wrong:
    L.append("| 줄 | 날짜 | 적힌 요일 | 실제 요일 |\n|---:|---|---|---|")
    for r in wd_wrong:
        L.append(f"| {r['_line']} | `{r['날짜']}` | `{r['요일']}` | {WEEKDAYS[r['_date'].weekday()]} |")
    L.append("")

L.append("## 3. 비고 열에 나오는 글\n")
L.append("| 비고 | 줄 수 |\n|---|---:|")
for k, v in memo_count.most_common():
    L.append(f"| `{k}` | {v} |")
L.append(f"| (빈칸) | {sum(1 for r in rows if not r['비고'].strip())} |\n")

L.append("## 4. 사람이 정해야 할 줄\n")
L.append("코드가 고른 줄: '불가능해 보이는 식수' 줄과 비고가 `수기 집계`인 줄.\n")
L.append("| 줄 | 날짜 | 출근예정 | 식수 | 비고 | 왜 걸렸나 |\n|---:|---|---:|---:|---|---|")
for line in sorted(decide):
    r = decide[line]
    meal, plan = to_int(r["식수"]), to_int(r["출근예정"])
    why = "식수 > 출근예정" if meal > plan else f"식수 < 출근예정의 20%({plan * LOW_RATIO:.1f})"
    L.append(f"| {line} | `{r['날짜']}` | {r['출근예정']} | {r['식수']} | {r['비고'] or '(빈칸)'} | {why} |")
L.append("")
L.append("- 비고가 `수기 집계`인 줄은 정제 R6에서 **`뺀다`** 또는 **`×10 보정`** 중 하나를 수강생이 프롬프트에 적어 정한다"
         "(AI가 정하지 않는다).")
L.append("- 나머지 줄은 R6 규칙대로라면 빠진다. 그대로 따를지 사람이 확인한다.")
if unjudged:
    L.append(f"- 출근예정이 빈칸이라 위 판정을 못 한 줄 {len(unjudged)}개는 R10(출근예정 채우기) 뒤에 R6로 다시 본다: "
             + ", ".join(f"줄 {r['_line']}" for r in unjudged))
if dup_unclear:
    L.append("- 같은 날짜 두 줄인데 값이 다르고 '재집계' 표시가 없는 날짜(R4는 나중 줄을 남김): "
             + ", ".join(str(d) for d in dup_unclear))
else:
    L.append("- 같은 날짜 두 줄 중 값이 다른 묶음은 모두 '재집계' 줄이 있어 R4로 정해진다(사람이 정할 묶음 없음).")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L) + "\n", encoding="utf-8")

# ---------- 화면 요약 ----------
print(f"데이터 {n_rows}줄 · 열 {len(columns)}개 · 날짜 {min(dates)} ~ {max(dates)} · 해석 못 한 날짜 {len(unparsed)}")
for name, cnt, _, detail in kinds:
    print(f"{name}: {cnt}  ({detail})")
print(f"적힌 요일 ≠ 실제 요일: {len(wd_wrong)} {[(r['_line'], r['날짜'], r['요일']) for r in wd_wrong]}")
print("비고:", dict(memo_count))
print("사람이 정할 줄:", [(r["_line"], r["날짜"], r["출근예정"], r["식수"], r["비고"]) for r in decide.values()])
print("출근예정 빈칸이라 판정 못 함:", [(r["_line"], r["날짜"], r["식수"]) for r in unjudged])
print("값 다르고 재집계 없는 중복 날짜:", dup_unclear)
print(f"보고서: {OUT.as_posix()}")
