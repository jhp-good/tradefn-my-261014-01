"""3일차 실습 C — 한빛식당(가상) 밥 예보 페이지를 계산해서 쓴다. 손으로 고치지 않는다.

실행: uv run python scripts/lunch_page.py
입력: workbench/day3/outputs/lunch_clean.csv · labs/day3/lab-c/nutritionist_memo.md (읽기만)
결과: workbench/day3/outputs/hanbit_lunch.html (같은 입력이면 같은 페이지)
기준: labs/day3/lab-c/lab_c_guide.md 「5. 감 검증」 · 「6. 페이지 규칙」 · 「7. 예보관 시험」 · 「8. 다음 주 예보」

지금 있는 구역: 머리 → 다음 주 예보 → 예보 성적표 → 영양사님 감 검증 → 만든 방법 (「10. 다듬기」)
"""
import html
import json
import math
import pathlib
import re
import sys

import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.linear_model import LinearRegression

sys.stdout.reconfigure(encoding="utf-8")

CLEAN = pathlib.Path("workbench/day3/outputs/lunch_clean.csv")
MEMO = pathlib.Path("labs/day3/lab-c/nutritionist_memo.md")
PLAN = pathlib.Path("labs/day3/lab-c/next_week_plan.csv")
OUT = pathlib.Path("workbench/day3/outputs/hanbit_lunch.html")

GAP = 2.0  # 100명당 2명 이상 차이 나면 '차이 있음'(사람이 정한 선)
CHART_JS = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"

# ---------- 읽기 ----------
df = pd.read_csv(CLEAN, encoding="utf-8-sig")
df["날짜"] = pd.to_datetime(df["날짜"])
df["rate"] = df["식수"] / df["출근예정"] * 100  # 출근 100명당 식수
period = f"{df['날짜'].min():%Y-%m-%d} ~ {df['날짜'].max():%Y-%m-%d}"

# 감 노트의 믿음 글 — "1. **글.** 덧말" 줄을 그대로 가져온다
memo_text = MEMO.read_text(encoding="utf-8")
BELIEF_TEXT = {int(n): re.sub(r"\*\*", "", t).strip()
               for n, t in re.findall(r"^(\d)\. (\*\*.+)$", memo_text, flags=re.M)}

# 행사가 없고 월급날이 아닌 날(보통 날)
normal = df[df["행사"].isna() & (df["월급날"] == 0)]


def mean_rate(sub):
    return round(float(sub["rate"].mean()), 4), int(len(sub))


def judge(diff, expected_sign):
    """믿음대로 2명 이상 → 맞음, 차이 2명 미만 → 반만, 반대로 2명 이상 → 틀림."""
    if abs(diff) < GAP:
        return "반만"
    return "맞음" if diff * expected_sign > 0 else "틀림"


def pair_belief(no, focus_name, focus, base_name, base, expected_sign, extra=""):
    (a, na), (b, nb) = mean_rate(focus), mean_rate(base)
    diff = a - b
    more = "많습니다" if diff > 0 else "적습니다"
    return {
        "no": no, "memo": BELIEF_TEXT.get(no, ""), "badge": judge(diff, expected_sign),
        "bars": [{"label": focus_name, "value": a, "n": na, "focus": True},
                 {"label": base_name, "value": b, "n": nb, "focus": False}],
        "line": f"{focus_name}이 {base_name}보다 100명당 {abs(diff):.1f}명 {more}." + extra,
        "diff": diff,
    }


beliefs = []

# 믿음 1 비 오는 날 vs 맑은 날 (비 오면 더 온다 → +)
beliefs.append(pair_belief(1, "비 오는 날", normal[normal["날씨"] == "비"],
                           "맑은 날", normal[normal["날씨"] == "맑음"], +1))

# 믿음 2 금요일 vs 월–목 (금요일은 덜 온다 → −)
beliefs.append(pair_belief(2, "금요일", normal[normal["요일"] == "금"],
                           "월–목", normal[normal["요일"].isin(list("월화수목"))], -1))

# 믿음 3 메뉴별(높은 순) — 돈가스가 1등이고 2등보다 2명 이상 많으면 맞음
menu = (normal.groupby("메인메뉴")["rate"].agg(["mean", "size"])
        .sort_values("mean", ascending=False))
ranked = [(m, round(float(r["mean"]), 4), int(r["size"])) for m, r in menu.iterrows()]
top_name, top_val, _ = ranked[0]
dk_rank = next(i for i, (m, _, _) in enumerate(ranked) if m == "돈가스")
dk_val = ranked[dk_rank][1]
if dk_rank == 0:
    rival_name, rival_val = ranked[1][0], ranked[1][1]
    badge3 = "맞음" if dk_val - rival_val >= GAP else "반만"
    line3 = f"돈가스가 1등이고, 2등 {rival_name}보다 100명당 {dk_val - rival_val:.1f}명 많습니다."
else:
    rival_name, rival_val = top_name, top_val
    badge3 = "반만" if top_val - dk_val < GAP else "틀림"
    line3 = (f"돈가스는 {len(ranked)}개 메뉴 중 {dk_rank + 1}등입니다. "
             f"1등 {top_name}보다 100명당 {top_val - dk_val:.1f}명 적습니다.")
beliefs.append({
    "no": 3, "memo": BELIEF_TEXT[3], "badge": badge3, "line": line3,
    "pair": [{"label": "돈가스", "value": dk_val}, {"label": rival_name, "value": rival_val}],
    "bars": [{"label": m, "value": v, "n": n, "focus": m == "돈가스"} for m, v, n in ranked],
    "diff": dk_val - rival_val,
})

# 믿음 4 최고기온 31도 이상 vs 25도 이상 31도 미만 (더우면 덜 온다 → −)
hot = normal[normal["최고기온"] >= 31]
warm = normal[(normal["최고기온"] >= 25) & (normal["최고기온"] < 31)]
beliefs.append(pair_belief(4, "31도 이상", hot, "25도 이상 31도 미만", warm, -1,
                           extra=f" 31도 이상인 날은 {len(hot)}일입니다."))

# 믿음 5 월요일 vs 화–목 (월요일은 덜 온다 → −)
beliefs.append(pair_belief(5, "월요일", normal[normal["요일"] == "월"],
                           "화–목", normal[normal["요일"].isin(list("화수목"))], -1))

# 메모에 없던 규칙: 월급날(월급날인 날 모두) vs 보통 날 — 믿음이 없어 배지 대신 '차이 있음/작음'
payday = df[df["월급날"] == 1]
pay = pair_belief(0, "월급날", payday, "보통 날", normal, 0)
pay.update(no=None, memo="월급날 — 영양사님 메모에는 없던 규칙입니다.",
           badge="차이 있음" if abs(pay["diff"]) >= GAP else "차이 작음")

# ---------- 예보관 시험 (「7. 예보관 시험」) ----------
TEST_START = pd.Timestamp("2026-09-14")  # 이 날 전 = 배우는 기간, 이 날부터 = 시험 기간
TEXT_COLS = ["요일", "날씨", "메인메뉴", "행사"]
FEATURE_COLS = ["요일", "날씨", "최고기온", "메인메뉴", "행사", "월급날", "출근예정"]
MENU_MULT = {"돈가스": 1.1, "카레": 1.1, "샐러드": 0.9}  # 나머지 1.0
BUFFER = 10  # AI 준비 = 예보 + 10
COST = 4500  # 1인분 원가(가정)
MARKS = {"2026-09-23": "추석 연휴 전날 · 돈가스", "2026-09-30": "비 오는 수요일 · 카레"}

df = df.sort_values("날짜").reset_index(drop=True)
train = df[df["날짜"] < TEST_START]
test = df[df["날짜"] >= TEST_START]
temp_fill = float(train["최고기온"].median())  # 최고기온 빈칸 = 배우는 기간의 가운데 값


def features(frame, cols=None):
    """재료 → 0/1 열. 시험 · 예보 때는 배울 때의 열(cols)로 맞추고 없는 열은 0."""
    X = frame[FEATURE_COLS].copy()
    X["최고기온"] = X["최고기온"].fillna(temp_fill)
    X["행사"] = X["행사"].fillna("없음")
    X = pd.get_dummies(X, columns=TEXT_COLS).astype(float)
    return X if cols is None else X.reindex(columns=cols, fill_value=0.0)


X_train = features(train)
X_test = features(test, X_train.columns)
y_train, y_test = train["식수"], test["식수"]

forecasters = {
    "선형 회귀": LinearRegression(),
    "LightGBM": LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=15,
                              min_child_samples=5, random_state=42, verbose=-1),
}
preds, scores = {}, {}
for name, model in forecasters.items():
    model.fit(X_train, y_train)
    preds[name] = model.predict(X_test)
    scores[name] = float((abs(preds[name] - y_test.to_numpy())).mean())  # 하루 평균 몇 인분 차이
ours = min(scores, key=scores.get)
ai_pred = preds[ours]


def nutritionist_formula(day, weekday, menu_name):
    """그날 전 같은 요일 실제 식수 4개(가장 가까운 날부터)의 평균 × 메뉴 배수."""
    prev = df[(df["날짜"] < day) & (df["요일"] == weekday)].tail(4)
    return float(prev["식수"].mean()) * MENU_MULT.get(menu_name, 1.0)


test_rows = []
for (_, r), p in zip(test.iterrows(), ai_pred):
    f = nutritionist_formula(r["날짜"], r["요일"], r["메인메뉴"])
    actual = int(r["식수"])
    ai_prep = float(p) + BUFFER
    test_rows.append({
        "date": f"{r['날짜']:%Y-%m-%d}", "label": f"{r['날짜']:%m/%d}({r['요일']})",
        "actual": actual, "ai": float(p), "formula": f,
        "ai_left": max(ai_prep - actual, 0.0), "ai_short": max(actual - ai_prep, 0.0),
        "f_left": max(f - actual, 0.0), "f_short": max(actual - f, 0.0),
    })
tdf = pd.DataFrame(test_rows)
result = {
    "ai": {"mae": scores[ours],
           "left": float(tdf["ai_left"].sum()), "short": float(tdf["ai_short"].sum()),
           "short_days": int((tdf["ai_short"] > 0).sum())},
    "formula": {"mae": float((tdf["formula"] - tdf["actual"]).abs().mean()),
                "left": float(tdf["f_left"].sum()), "short": float(tdf["f_short"].sum()),
                "short_days": int((tdf["f_short"] > 0).sum())},
}

# ---------- 다음 주 예보 (「8. 다음 주 예보」) ----------
WEEKDAYS = "월화수목금토일"


def round_half_up(x):
    return int(math.floor(x + 0.5))


plan = pd.read_csv(PLAN, encoding="utf-8-sig")
plan["날짜"] = pd.to_datetime(plan["날짜"])
assert all(WEEKDAYS[d.weekday()] == w for d, w in zip(plan["날짜"], plan["요일"])), "계획표 요일이 날짜와 다름"
plan = plan.rename(columns={"날씨예보": "날씨", "최고기온예보": "최고기온"})
plan["월급날"] = (plan["월급날"].fillna("") == "Y").astype(int)  # Y → 1, 빈칸 → 0
X_plan = features(plan, X_train.columns)  # 행사 빈칸 → '없음', 배울 때와 같은 열
plan_pred = forecasters[ours].predict(X_plan)  # 시험에서 고른 우리 예보관(배우는 기간으로 배운 그대로)

# 코멘트 근거 — 감 검증에서 계산한 숫자만 끼워 넣는다
B = {b["no"]: b for b in beliefs}
menu_rank = {m: i for i, (m, _, _) in enumerate(ranked)}
menu_val = {m: v for m, v, _ in ranked}


def josa(word, with_final, without_final):
    """마지막 글자에 받침이 있으면 with_final(이 · 은), 없으면 without_final(가 · 는)."""
    c = ord(word[-1]) - 0xAC00
    return word + (with_final if 0 <= c <= 11171 and c % 28 else without_final)


def evidence(r):
    if r["월급날"] == 1:
        return f"월급날은 보통 날보다 100명당 {abs(pay['diff']):.1f}명 적게 오셨어요"
    if r["날씨"] == "비":
        return f"비 오는 날은 맑은 날보다 100명당 {abs(B[1]['diff']):.1f}명 더 오셨어요"
    if r["요일"] == "금":
        return f"금요일은 월–목보다 100명당 {abs(B[2]['diff']):.1f}명 적게 오셨어요"
    if pd.notna(r["행사"]):
        return f"{josa(r['행사'], '이', '가')} 있어 출근예정이 {r['출근예정']}명이에요"
    m = r["메인메뉴"]
    if m in menu_rank and menu_rank[m] in (0, len(ranked) - 1):
        where = "가장 높았어요" if menu_rank[m] == 0 else "가장 낮았어요"
        return f"{josa(m, '은', '는')} 메뉴 중 100명당 식수가 {where}({menu_val[m]:.1f}명)"
    if r["요일"] == "월":
        return f"월요일은 화–목보다 100명당 {abs(B[5]['diff']):.1f}명 더 오셨어요(감 검증 '틀림')"
    return "특별한 조건이 없는 날이에요"


week = []
for (_, r), p in zip(plan.iterrows(), plan_pred):
    fc = round_half_up(float(p))
    f = round_half_up(nutritionist_formula(r["날짜"], r["요일"], r["메인메뉴"]))
    prep = fc + BUFFER
    gap = prep - f
    gap_txt = (f"AI 준비 {prep}인분은 공식보다 {abs(gap)}인분 {'많아요' if gap > 0 else '적어요'}" if gap
               else f"AI 준비 {prep}인분은 공식과 같아요")
    badges = [r["날씨"], r["메인메뉴"]] + ([r["행사"]] if pd.notna(r["행사"]) else []) + (["월급날"] if r["월급날"] else [])
    week.append({"date": f"{r['날짜']:%Y-%m-%d}", "md": f"{r['날짜'].month}/{r['날짜'].day}", "dow": r["요일"],
                 "forecast": fc, "prep": prep, "formula": f, "badges": badges,
                 "comment": f"영양사님, {evidence(r)}. {gap_txt}."})
hi = max(range(len(week)), key=lambda i: week[i]["forecast"])
lo = min(range(len(week)), key=lambda i: week[i]["forecast"])


# ---------- 페이지 조각 ----------
def esc(s):
    return html.escape(str(s))


def fmt(v):
    return f"{v:.1f}"


def card(b, idx):
    kind = {"맞음": "ok", "반만": "half", "틀림": "bad"}.get(b["badge"], "note")
    title = f"믿음 {b['no']}" if b["no"] else "메모에 없던 규칙"
    shown = b.get("pair") or b["bars"]
    nums = "".join(
        f'<div class="num"><span class="num-label">{esc(x["label"])}</span>'
        f'<span class="num-val">{fmt(x["value"])}<small>명</small></span>'
        + (f'<span class="num-n">{x["n"]}일</span>' if "n" in x else "") + "</div>"
        for x in shown)
    height = 44 + 30 * len(b["bars"])
    return f"""
      <article class="card">
        <header class="card-head">
          <span class="card-no">{esc(title)}</span>
          <span class="badge badge-{kind}">{esc(b['badge'])}</span>
        </header>
        <p class="memo">{f"“{esc(b['memo'])}”" if b["no"] else esc(b["memo"])}</p>
        <div class="nums">{nums}</div>
        <div class="chart" style="height:{height}px"><canvas id="chart-{idx}" aria-label="{esc(title)} 막대 그래프"></canvas></div>
        <p class="verdict">{esc(b['line'])}</p>
      </article>"""


def section_beliefs():
    cards = [card(b, i) for i, b in enumerate(beliefs)] + [card(pay, len(beliefs))]
    tally = {k: sum(b["badge"] == k for b in beliefs) for k in ("맞음", "반만", "틀림")}
    return f"""
    <section id="beliefs">
      <h2>영양사님 감 검증</h2>
      <p class="lead">출근 인원이 다른 날도 견줄 수 있게 <b>출근 100명당 식수</b>(식수 ÷ 출근예정 × 100, 날마다 구해 평균)로 비교했습니다.
        행사가 없고 월급날이 아닌 날 {len(normal)}일만 썼습니다. 100명당 2명 이상 차이 나면 '차이 있음'으로 봅니다(사람이 정한 선).</p>
      <p class="tally">맞음 {tally['맞음']} · 반만 {tally['반만']} · 틀림 {tally['틀림']}</p>
      <div class="grid">{''.join(cards)}
      </div>
    </section>"""


def section_week():
    cards = []
    for i, w in enumerate(week):
        flag = ('<span class="flag flag-hi">이번 주 가장 많은 날</span>' if i == hi
                else '<span class="flag flag-lo">이번 주 가장 적은 날</span>' if i == lo else "")
        tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in w["badges"])
        cards.append(f"""
        <article class="card day{' day-hi' if i == hi else ''}{' day-lo' if i == lo else ''}">
          <div class="day-head"><span class="day-date">{w['md']}</span><span class="day-dow">{w['dow']}요일</span></div>
          {flag}
          <p class="day-big">{w['forecast']}<small>명</small></p>
          <p class="day-prep">준비 {w['prep']}인분</p>
          <p class="day-formula">영양사님 공식이면 {w['formula']}인분</p>
          <div class="tags">{tags}</div>
          <p class="day-comment">{esc(w['comment'])}</p>
        </article>""")
    return f"""
    <section id="week">
      <h2>다음 주 예보 ({week[0]['md']} ~ {week[-1]['md']})</h2>
      <p class="lead">시험에서 이긴 우리 예보관({esc(ours)})에게 다음 주 계획을 물었습니다. 예보는 반올림, 준비 = 예보 + {BUFFER}인분.
        영양사님 공식은 그날 전 같은 요일 4번의 평균 × 메뉴 배수입니다. 준비량은 영양사님이 정합니다.</p>
      <div class="week">{''.join(cards)}
      </div>
    </section>"""


def section_score():
    names = list(scores)
    model_cards = "".join(
        f'<div class="num{" num-pick" if n == ours else ""}"><span class="num-label">{esc(n)}'
        + (' · <b>우리 예보관</b>' if n == ours else "") + "</span>"
        f'<span class="num-val">{fmt(scores[n])}<small>인분</small></span>'
        '<span class="num-n">시험 20일 하루 평균 차이</span></div>'
        for n in names)
    marks = "".join(
        f"<li><b>{r['label']} {esc(MARKS[r['date']])}</b> — 실제 {r['actual']}명 · "
        f"우리 예보관 {r['ai']:.0f}명 · 영양사님 공식 {r['formula']:.0f}인분</li>"
        for r in test_rows if r["date"] in MARKS)
    a, f = result["ai"], result["formula"]

    def won(x):
        return f"{round(x) * COST:,}원"

    def vs(label, av, fv, unit, note_a="", note_f="", who_a=f"AI 준비(예보 + {BUFFER})"):
        return f"""
        <article class="card vs">
          <h3>{esc(label)}</h3>
          <div class="nums">
            <div class="num num-pick"><span class="num-label">{esc(who_a)}</span>
              <span class="num-val">{av}<small>{unit}</small></span><span class="num-n">{note_a}</span></div>
            <div class="num"><span class="num-label">영양사님 공식</span>
              <span class="num-val">{fv}<small>{unit}</small></span><span class="num-n">{note_f}</span></div>
          </div>
        </article>"""

    cards = (vs("하루 평균 몇 인분 차이", fmt(a["mae"]), fmt(f["mae"]), "인분",
                "예보와 실제의 차이", "공식과 실제의 차이", who_a=f"AI(우리 예보관)")
             + vs("남은 밥(20일 합)", f"{round(a['left']):,}", f"{round(f['left']):,}", "인분",
                  won(a["left"]), won(f["left"]))
             + vs("모자란 밥(20일 합) = 컵라면을 드신 분", f"{round(a['short']):,}", f"{round(f['short']):,}", "인분",
                  f"모자란 날 {a['short_days']}일", f"모자란 날 {f['short_days']}일"))
    return f"""
    <section id="score">
      <h2>예보 성적표</h2>
      <p class="lead">{TEST_START:%Y-%m-%d} 전까지의 기록 {len(train)}일로 배우고, 그 뒤 {len(test_rows)}일({test_rows[0]['date']} ~ {test_rows[-1]['date']})로 시험했습니다.
        시험 기간은 배울 때 쓰지 않았습니다. 예보관 설정은 모두 같은 결과를 보려고 고정했습니다.</p>
      <div class="nums models">{model_cards}</div>
      <p class="tally">복잡한 쪽이 늘 이기지는 않는다 — 시험으로 고른다</p>
      <article class="card">
        <h3>시험 {len(test_rows)}일 — 실제 · 우리 예보관({esc(ours)}) · 영양사님 공식</h3>
        <div class="chart" style="height:300px"><canvas id="chart-test" aria-label="시험 기간 선 그래프"></canvas></div>
        <ul class="marks">{marks}</ul>
      </article>
      <div class="grid vs-grid">{cards}
      </div>
      <p class="lead">준비 = AI는 우리 예보관의 예보 + {BUFFER}인분, 영양사님은 공식 그대로. 남은 밥 = 준비 − 실제, 모자란 밥 = 실제 − 준비(0보다 작으면 0).
        1인분 원가 {COST:,}원(가정).</p>
    </section>"""


def section_method():
    other = next(n for n in scores if n != ours)
    return f"""
    <section id="method">
      <h2>만든 방법</h2>
      <ul class="method">
        <li>데이터: (가상) 한빛정밀(주) 본사 구내식당의 가상 점심 기록 · 기록 기간 {nowrap_period()} · 정제 뒤 {len(df)}줄</li>
        <li>예보관 두 명: 선형 회귀와 LightGBM — 시험 {len(test_rows)}일 성적이 더 좋은 <b>{esc(ours)}</b>를 골랐습니다(하루 평균 차이 {esc(ours)} {fmt(scores[ours])}인분 · {esc(other)} {fmt(scores[other])}인분).</li>
        <li>설정은 모두 같은 결과를 보려고 고정했습니다.</li>
        <li>결정은 영양사님이 합니다. 이 페이지는 준비량을 정하는 데 참고하는 자료입니다.</li>
        <li>모든 숫자는 scripts/lunch_page.py가 정제한 기록(lunch_clean.csv)에서 계산했습니다. 회사 · 식당 · 인물은 모두 가상입니다.</li>
      </ul>
    </section>"""


def nowrap_period():
    a, b = period.split(" ~ ")
    return f'<span class="nw">{a}</span> ~ <span class="nw">{b}</span>'


CSS = """
:root{--bg:#f5f6f8;--card:#ffffff;--ink:#1f2328;--muted:#5b616b;--line:#e3e6ea;
--accent:#2563eb;--accent-soft:#dbe6fd;--warn:#c2410c;--warn-soft:#fde4d6;--gray:#9aa1ab;--gray-soft:#eceef1}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Noto Sans KR',sans-serif;
font-size:16px;line-height:1.6;word-break:keep-all;overflow-wrap:break-word}
.wrap{max-width:1080px;margin:0 auto;padding:24px 16px 48px}
.head h1{margin:0 0 4px;font-size:28px;line-height:1.3}
.head p{margin:0;color:var(--muted)}
section{margin-top:32px}
h2{font-size:22px;margin:0 0 8px}
.lead{margin:0 0 8px;color:var(--muted)}
.tally{margin:0 0 16px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}
.card-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.card-no{font-weight:700;color:var(--muted);font-size:14px}
.badge{font-size:14px;font-weight:700;padding:2px 10px;border-radius:999px;white-space:nowrap}
.badge-ok{background:var(--accent-soft);color:var(--accent)}
.badge-half{background:var(--gray-soft);color:var(--muted)}
.badge-bad{background:var(--warn-soft);color:var(--warn)}
.badge-note{background:var(--gray-soft);color:var(--ink)}
.memo{margin:8px 0 12px;font-weight:700;font-size:17px}
.nums{display:flex;gap:12px;flex-wrap:wrap}
.num{flex:1 1 120px;background:var(--bg);border-radius:8px;padding:8px 10px;min-width:0}
.num-label{display:block;font-size:14px;color:var(--muted)}
.num-val{display:block;font-size:24px;font-weight:700;line-height:1.3}
.num-val small{font-size:14px;font-weight:400;margin-left:2px}
.num-n{display:block;font-size:14px;color:var(--muted)}
.chart{position:relative;margin-top:12px}
.verdict{margin:8px 0 0}
.foot{margin-top:32px;color:var(--muted);font-size:14px}
h3{font-size:17px;margin:0 0 8px}
.models{margin:12px 0 8px}
.num-pick{background:var(--accent-soft)}
#score .card{margin-top:16px}
.vs-grid{margin-top:0}
.marks{margin:12px 0 0;padding-left:20px}
.marks li{margin-top:4px}
.week{display:grid;grid-template-columns:1fr;gap:12px}
@media (min-width:960px){.week{grid-template-columns:repeat(5,minmax(0,1fr))}}
.day{display:flex;flex-direction:column;gap:4px}
.day-hi{border:2px solid var(--accent)}
.day-lo{border:2px solid var(--warn)}
.day-head{display:flex;justify-content:space-between;align-items:baseline}
.day-date{font-size:20px;font-weight:700}
.day-dow{color:var(--muted)}
.flag{align-self:flex-start;font-size:14px;font-weight:700;padding:2px 10px;border-radius:999px}
.flag-hi{background:var(--accent-soft);color:var(--accent)}
.flag-lo{background:var(--warn-soft);color:var(--warn)}
.day-big{margin:4px 0 0;font-size:40px;font-weight:700;line-height:1.1}
.day-big small{font-size:18px;font-weight:400;margin-left:2px}
.day-prep{margin:0;font-size:18px;font-weight:700}
.day-formula{margin:0;font-size:14px;color:var(--muted)}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.tag{font-size:14px;padding:1px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg)}
.day-comment{margin:8px 0 0;font-size:15px}
.nw{white-space:nowrap}
.method{margin:0;padding-left:20px;color:var(--muted)}
.method li{margin-top:4px}
"""

JS = """
const DATA = JSON.parse(document.getElementById('page-data').textContent);
const css = getComputedStyle(document.documentElement);
const C = n => css.getPropertyValue(n).trim();
Chart.defaults.font.family = "'Noto Sans KR', sans-serif";
Chart.defaults.font.size = 14;
Chart.defaults.color = C('--muted');
DATA.cards.forEach((b, i) => {
  const el = document.getElementById('chart-' + i);
  if (!el) return;
  new Chart(el, {
    type: 'bar',
    data: {
      labels: b.bars.map(x => x.label),
      datasets: [{
        data: b.bars.map(x => x.value),
        backgroundColor: b.bars.map(x => x.focus ? C('--accent') : C('--gray')),
        borderRadius: 4, borderSkipped: 'start', barThickness: 18
      }]
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => '100명당 ' + c.parsed.x.toFixed(1) + '명 (' + b.bars[c.dataIndex].n + '일)' } }
      },
      scales: {
        x: { beginAtZero: true, max: 100, grid: { color: C('--line') }, ticks: { stepSize: 25 } },
        y: { grid: { display: false } }
      }
    }
  });
});

// 예보 성적표 — 시험 기간 선 그래프, 9/23 · 9/30에 세로 점선 표시
(() => {
  const el = document.getElementById('chart-test');
  if (!el) return;
  const T = DATA.test;
  const markIdx = T.days.map((d, i) => T.marks[d] ? i : -1).filter(i => i >= 0);
  const markLines = {
    id: 'markLines',
    afterDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      ctx.save();
      ctx.strokeStyle = C('--warn'); ctx.fillStyle = C('--warn');
      ctx.setLineDash([4, 4]); ctx.lineWidth = 1.5;
      ctx.font = "14px 'Noto Sans KR', sans-serif"; ctx.textAlign = 'center';
      markIdx.forEach(i => {
        const x = scales.x.getPixelForValue(i);
        ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
        const [m, d] = T.days[i].slice(5).split('-').map(Number);
        ctx.fillText(m + '/' + d, x, chartArea.top - 10);  // 그래프 위 여백에 — 점과 겹치지 않게
      });
      ctx.restore();
    }
  };
  new Chart(el, {
    type: 'line',
    data: {
      labels: T.labels,
      datasets: [
        { label: '실제', data: T.actual, borderColor: C('--ink'), backgroundColor: C('--ink'),
          borderWidth: 2, pointRadius: T.days.map((d, i) => markIdx.includes(i) ? 5 : 3) },
        { label: '우리 예보관(' + T.ours + ')', data: T.ai, borderColor: C('--accent'), backgroundColor: C('--accent'),
          borderWidth: 2, pointRadius: 3 },
        { label: '영양사님 공식', data: T.formula, borderColor: C('--gray'), backgroundColor: C('--gray'),
          borderWidth: 2, borderDash: [6, 4], pointRadius: 3 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      layout: { padding: { top: 26 } },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14 } },
        tooltip: { callbacks: {
          title: items => { const i = items[0].dataIndex; return T.labels[i] + (T.marks[T.days[i]] ? ' · ' + T.marks[T.days[i]] : ''); },
          label: c => c.dataset.label + ' ' + Math.round(c.parsed.y) + '명'
        } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, callback: (v, i) => T.labels[i].slice(0, 5) } },
        y: { grid: { color: C('--line') }, ticks: { callback: v => v + '명' } }
      }
    },
    plugins: [markLines]
  });
})();
"""


def page(sections, data):
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>한빛식당 밥 예보</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main class="wrap">
  <header class="head">
    <h1>한빛식당 밥 예보</h1>
    <p>(가상) 한빛정밀(주) 본사 구내식당 · 기록 기간 {nowrap_period()} · 만든 사람 총무팀 <span class="nw">최 대리(가상)</span></p>
  </header>
{''.join(sections)}
</main>
<script type="application/json" id="page-data">{json.dumps(data, ensure_ascii=False)}</script>
<script src="{CHART_JS}"></script>
<script>{JS}</script>
</body>
</html>
"""


all_cards = beliefs + [pay]
data = {"period": period, "normal_days": len(normal),
        "cards": [{"no": b["no"], "badge": b["badge"], "bars": b["bars"]} for b in all_cards],
        "test": {"ours": ours, "days": [r["date"] for r in test_rows], "labels": [r["label"] for r in test_rows],
                 "actual": [r["actual"] for r in test_rows],
                 "ai": [round(r["ai"], 1) for r in test_rows],
                 "formula": [round(r["formula"], 1) for r in test_rows],
                 "marks": MARKS},
        "week": week}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page([section_week(), section_score(), section_beliefs(), section_method()], data), encoding="utf-8")

# ---------- 화면 요약 ----------
print(f"기록 기간 {period} · 전체 {len(df)}일 · 보통 날 {len(normal)}일")
for b in all_cards:
    shown = b.get("pair") or b["bars"]
    nums = " vs ".join(f"{x['label']} {x['value']:.2f}" + (f"({x['n']}일)" if "n" in x else "") for x in shown)
    print(f"{'믿음 ' + str(b['no']) if b['no'] else '월급날'}: {nums} · 차이 {b['diff']:+.2f} → {b['badge']}")
print("메뉴 순위:", [(m, round(v, 2), n) for m, v, n in ranked])
print(f"31도 이상 날 수(보통 날): {len(hot)}")
print(f"배우는 기간 {len(train)}일 · 시험 기간 {len(test)}일 · 재료 열 {X_train.shape[1]}개 · 최고기온 빈칸 채움 {temp_fill}")
print("시험 성적(하루 평균 몇 인분 차이):", {k: round(v, 2) for k, v in scores.items()}, "→ 우리 예보관:", ours)
for r in test_rows:
    if r["date"] in MARKS:
        print(f"{r['date']} 실제 {r['actual']} · AI 예보 {r['ai']:.1f} · 공식 {r['formula']:.1f}")
for k, v in result.items():
    print(f"{k}: MAE {v['mae']:.2f} · 남은 {v['left']:.1f}인분({round(v['left']) * COST:,}원) · "
          f"모자란 {v['short']:.1f}인분 · 모자란 날 {v['short_days']}")
print("다음 주 예보:")
for (_, r), p, w in zip(plan.iterrows(), plan_pred, week):
    print(f"  {w['date']}({w['dow']}) 예보 {p:.2f} → {w['forecast']}명 · 준비 {w['prep']} · 공식 "
          f"{nutritionist_formula(r['날짜'], r['요일'], r['메인메뉴']):.2f} → {w['formula']} · {w['comment']}")
print(f"가장 많은 날 {week[hi]['date']} {week[hi]['forecast']}명 · 가장 적은 날 {week[lo]['date']} {week[lo]['forecast']}명")
print("구역 순서:", re.findall(r'<section id="(\w+)"', OUT.read_text(encoding="utf-8")))
print(f"페이지: {OUT.as_posix()}")
