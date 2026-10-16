"""3일차 실습 C — 한빛식당(가상) 밥 예보 페이지를 계산해서 쓴다. 손으로 고치지 않는다.

실행: uv run python scripts/lunch_page.py
입력: workbench/day3/outputs/lunch_clean.csv · labs/day3/lab-c/nutritionist_memo.md (읽기만)
결과: workbench/day3/outputs/hanbit_lunch.html (같은 입력이면 같은 페이지)
기준: labs/day3/lab-c/lab_c_guide.md 「5. 감 검증」 · 「6. 페이지 규칙」

지금 있는 구역: 머리 → 영양사님 감 검증
"""
import html
import json
import pathlib
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

CLEAN = pathlib.Path("workbench/day3/outputs/lunch_clean.csv")
MEMO = pathlib.Path("labs/day3/lab-c/nutritionist_memo.md")
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
    <p>(가상) 한빛정밀(주) 본사 구내식당 · 기록 기간 {period} · 만든 사람 총무팀 최 대리(가상)</p>
  </header>
{''.join(sections)}
  <p class="foot">모든 숫자는 scripts/lunch_page.py가 정제한 기록(lunch_clean.csv)에서 계산했습니다. 회사 · 식당 · 인물은 모두 가상입니다.</p>
</main>
<script type="application/json" id="page-data">{json.dumps(data, ensure_ascii=False)}</script>
<script src="{CHART_JS}"></script>
<script>{JS}</script>
</body>
</html>
"""


all_cards = beliefs + [pay]
data = {"period": period, "normal_days": len(normal),
        "cards": [{"no": b["no"], "badge": b["badge"], "bars": b["bars"]} for b in all_cards]}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page([section_beliefs()], data), encoding="utf-8")

# ---------- 화면 요약 ----------
print(f"기록 기간 {period} · 전체 {len(df)}일 · 보통 날 {len(normal)}일")
for b in all_cards:
    shown = b.get("pair") or b["bars"]
    nums = " vs ".join(f"{x['label']} {x['value']:.2f}" + (f"({x['n']}일)" if "n" in x else "") for x in shown)
    print(f"{'믿음 ' + str(b['no']) if b['no'] else '월급날'}: {nums} · 차이 {b['diff']:+.2f} → {b['badge']}")
print("메뉴 순위:", [(m, round(v, 2), n) for m, v, n in ranked])
print(f"31도 이상 날 수(보통 날): {len(hot)}")
print(f"페이지: {OUT.as_posix()}")
