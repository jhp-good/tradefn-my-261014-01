"""3일차 실습 D — 바이어 리스크 한눈에(v1). CSV를 읽어 계산하고 HTML 한 장을 쓴다. HTML은 손으로 고치지 않는다.

실행: uv run python scripts/board_page.py
입력: labs/day3/lab-d/buyer_board.csv (읽기만)
결과: workbench/day3/outputs/buyer_board.html (같은 입력이면 같은 결과)
기준: labs/day3/lab-d/lab_d_guide.md 「3. 첫 화면 v1」 · 「4. 결과 페이지 규칙」, 토큰은 workbench/day3/outputs/design.md
"""
import html
import json
import math
import pathlib
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# design.md 토큰 표 그대로 — 이 값만 쓴다
TOKENS = {
    "color-bg": "#F6F7F9",
    "color-surface": "#FFFFFF",
    "color-border": "#D5DAE0",
    "color-text": "#1F2328",
    "color-text-muted": "#5A626C",
    "color-accent": "#1D4ED8",
    "grade-s": "#1E7B3C",
    "grade-a": "#5F7209",
    "grade-b": "#B45309",
    "grade-c": "#B91C1C",
    "font-family": "'Noto Sans KR', sans-serif",
    "fs-1": "14px",
    "fs-2": "16px",
    "fs-3": "18px",
    "fs-4": "22px",
    "fs-5": "28px",
    "fs-6": "36px",
    "space-1": "4px",
    "space-2": "8px",
    "space-3": "12px",
    "space-4": "16px",
    "space-5": "24px",
    "space-6": "32px",
    "space-7": "48px",
    "radius-1": "4px",
    "radius-2": "8px",
    "shadow": "none",
}
PHONE_MAX = 640  # 이 폭 이하는 휴대폰 배치(design.md 토큰 표 밖의 값 — 알림)

SRC = pathlib.Path("labs/day3/lab-d/buyer_board.csv")
OUT = pathlib.Path("workbench/day3/outputs/buyer_board.html")
AS_OF = "2026-09-30"
BASE_LINE = 17  # 위험 선 처음 값(%)
LINE_MIN, LINE_MAX = 5, 30
GRADES = ["S", "A", "B", "C"]

COUNTRY_KO = {
    "ARE": "아랍에미리트", "BRA": "브라질", "CHN": "중국", "DEU": "독일", "EGY": "이집트",
    "GBR": "영국", "IDN": "인도네시아", "IND": "인도", "JPN": "일본", "MEX": "멕시코",
    "MYS": "말레이시아", "NGA": "나이지리아", "NLD": "네덜란드", "POL": "폴란드", "SAU": "사우디아라비아",
    "THA": "태국", "TUR": "튀르키예", "TWN": "대만", "USA": "미국", "VNM": "베트남",
}


def grade_of(pd_30d, line_pct):
    """C부터 검사: 선 이상 C · 선의 절반 이상 B · 4분의 1 이상 A · 나머지 S."""
    t = line_pct / 100
    if pd_30d >= t:
        return "C"
    if pd_30d >= t / 2:
        return "B"
    if pd_30d >= t / 4:
        return "A"
    return "S"


def usd(n):
    return f"${int(n):,}"


def pct1(x):
    return f"{x:.1f}%"


def esc(s):
    return html.escape(str(s))


def clean(v):
    return None if isinstance(v, float) and math.isnan(v) else v


# ---------- 읽기 · 계산 ----------
df = pd.read_csv(SRC, encoding="utf-8-sig")
unknown = sorted(set(df["country_code"]) - set(COUNTRY_KO))
if unknown:
    raise SystemExit(f"한글 나라 이름 표에 없는 코드: {unknown} — 확인 필요")
df["country_ko"] = df["country_code"].map(COUNTRY_KO)
df["grade_now"] = [grade_of(p, BASE_LINE) for p in df["pd_30d"]]
match = int((df["grade_now"] == df["grade"]).sum())

total_ar = int(df["open_ar_usd"].sum())
overdue_sum = int(df["overdue_usd"].sum())
overdue_n = int((df["overdue_usd"] > 0).sum())


def state(line_pct):
    g = [grade_of(p, line_pct) for p in df["pd_30d"]]
    sub = df.assign(g=g)
    cnt = {k: int((sub["g"] == k).sum()) for k in GRADES}
    ar = {k: int(sub.loc[sub["g"] == k, "open_ar_usd"].sum()) for k in GRADES}
    region_c = sub[sub["g"] == "C"].groupby("region")["open_ar_usd"].sum().to_dict()
    return {"cnt": cnt, "ar": ar, "region_c": {k: int(v) for k, v in region_c.items()}, "g": g}


base = state(BASE_LINE)
regions = (df.groupby("region")["open_ar_usd"].sum().sort_values(ascending=False))
region_rows = [(r, int(v)) for r, v in regions.items()]
top10 = df.sort_values("pd_30d", ascending=False).head(10)

buyers = [{
    "id": r.buyer_id, "name": r.buyer_name, "country": r.country_ko, "region": r.region,
    "ar": clean(r.open_ar_usd), "od": clean(r.overdue_usd), "pd": clean(r.pd_30d), "signal": clean(r.signal_1),
} for r in df.itertuples()]
data = {
    "base": BASE_LINE, "total_ar": total_ar, "buyers": buyers,
    "top10": list(top10["buyer_id"]), "regions": [r for r, _ in region_rows],
}


# ---------- 페이지 조각 (처음 17% 화면) ----------
def badge(g):
    return f'<span class="badge g-{g}">{g}</span>'


def kpi(label, num_id, num, sub_id, sub):
    return (f'<article class="kpi"><p class="kpi-label">{esc(label)}</p>'
            f'<p class="kpi-num fit" id="{num_id}">{esc(num)}</p>'
            f'<p class="kpi-sub" id="{sub_id}">{esc(sub)}</p></article>')


c_cnt, c_ar = base["cnt"]["C"], base["ar"]["C"]
kpis = "".join([
    kpi("위험 바이어(C등급)", "k-c-n", f"{c_cnt}곳", "k-c-n-sub", f"위험 선 {BASE_LINE}% 이상"),
    kpi("C등급 채권", "k-c-ar", usd(c_ar), "k-c-ar-sub", f"전체 채권의 {pct1(c_ar / total_ar * 100)}"),
    kpi("전체 채권", "k-tot", usd(total_ar), "k-tot-sub", f"{len(df)}곳"),
    kpi("연체 금액", "k-od", usd(overdue_sum), "k-od-sub", f"연체가 있는 곳 {overdue_n}곳"),
])

seg = "".join(
    f'<span class="seg g-{g}" id="seg-{g}" style="width:{base["cnt"][g] / len(df) * 100:.4f}%" '
    f'title="{g} {base["cnt"][g]}곳"></span>' for g in GRADES)
legend = "".join(
    f'<li class="legend-row">{badge(g)}<span class="legend-n num" id="lg-n-{g}">{base["cnt"][g]}곳</span>'
    f'<span class="legend-ar num" id="lg-ar-{g}">{usd(base["ar"][g])}</span></li>' for g in GRADES)

rows, cards = [], []
for r in top10.itertuples():
    g = grade_of(r.pd_30d, BASE_LINE)
    sig = esc(r.signal_1) if isinstance(r.signal_1, str) else "–"
    rows.append(
        f'<tr><td class="t-name">{esc(r.buyer_name)}</td><td>{esc(r.country_ko)}</td>'
        f'<td data-gcell="{r.buyer_id}">{badge(g)}</td><td class="num">{pct1(r.pd_30d * 100)}</td>'
        f'<td class="num">{usd(r.open_ar_usd)}</td><td class="num">{usd(r.overdue_usd)}</td>'
        f'<td class="t-sig">{sig}</td></tr>')
    cards.append(
        f'<li class="bcard"><div class="bcard-top"><span class="bcard-name">{esc(r.buyer_name)}</span>'
        f'<span data-gcell="{r.buyer_id}">{badge(g)}</span></div>'
        f'<p class="bcard-line"><span>{esc(r.country_ko)}</span><span class="num">위험 점수 {pct1(r.pd_30d * 100)}</span></p>'
        f'<p class="bcard-line"><span class="muted">채권</span><span class="num">{usd(r.open_ar_usd)}</span></p>'
        f'<p class="bcard-line"><span class="muted">연체</span><span class="num">{usd(r.overdue_usd)}</span></p>'
        f'<p class="bcard-sig">{sig}</p></li>')

max_region = region_rows[0][1]
reg = "".join(
    f'<li class="reg-row"><div class="reg-head"><span class="reg-name">{esc(r)}</span>'
    f'<span class="num reg-amt">{usd(v)}</span></div>'
    f'<div class="reg-track" style="width:{v / max_region * 100:.4f}%">'
    f'<span class="reg-c" id="rc-{i}" style="width:{base["region_c"].get(r, 0) / v * 100 if v else 0:.4f}%"></span></div>'
    f'<p class="reg-sub">C등급 <span class="num" id="rc-amt-{i}">{usd(base["region_c"].get(r, 0))}</span></p></li>'
    for i, (r, v) in enumerate(region_rows))

root = "\n".join(f"  --{k}: {v};" for k, v in TOKENS.items())

CSS = f"""
:root {{
{root}
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--color-bg); color: var(--color-text); font-family: var(--font-family);
  font-size: var(--fs-2); line-height: 1.5; word-break: keep-all; overflow-wrap: break-word; }}
.wrap {{ padding: var(--space-7) var(--space-6); }}
h1, h2, p, ul {{ margin: 0; }}
ul {{ list-style: none; padding: 0; }}
.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; text-align: right; }}
.muted {{ color: var(--color-text-muted); }}
.head h1 {{ font-size: var(--fs-5); font-weight: 700; color: var(--color-text); }}
.head p {{ margin-top: var(--space-2); font-size: var(--fs-1); color: var(--color-text-muted); }}
section {{ margin-top: var(--space-6); }}
.sec-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-2) var(--space-4);
  flex-wrap: wrap; margin-bottom: var(--space-4); }}
.sec-head h2 {{ font-size: var(--fs-4); font-weight: 700; color: var(--color-text); }}
.sec-note {{ font-size: var(--fs-1); color: var(--color-text-muted); }}
.card {{ background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-2);
  box-shadow: var(--shadow); padding: var(--space-5); min-width: 0; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-5); margin-top: var(--space-6); }}
.kpi {{ background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-2);
  padding: var(--space-4) var(--space-5); min-width: 0; }}
.kpi-label {{ font-size: var(--fs-1); color: var(--color-text-muted); }}
.kpi-num {{ margin-top: var(--space-2); font-size: var(--fs-6); font-weight: 700; line-height: 1.2; color: var(--color-text);
  font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; }}
.kpi-num.fs-down-1 {{ font-size: var(--fs-5); }}
.kpi-num.fs-down-2 {{ font-size: var(--fs-4); }}
.kpi-num.fs-down-3 {{ font-size: var(--fs-3); }}
.kpi-sub {{ margin-top: var(--space-1); font-size: var(--fs-1); color: var(--color-text-muted); white-space: nowrap; }}
.row2 {{ display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: var(--space-5); }}
.gbar {{ display: flex; height: var(--space-6); border-radius: var(--radius-1); overflow: hidden; gap: 0; }}
.seg {{ display: block; height: 100%; }}
.g-S {{ background: var(--grade-s); }} .g-A {{ background: var(--grade-a); }}
.g-B {{ background: var(--grade-b); }} .g-C {{ background: var(--grade-c); }}
.legend {{ margin-top: var(--space-4); display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); }}
.legend-row {{ display: flex; flex-direction: column; gap: var(--space-1); min-width: 0; }}
.legend-n {{ text-align: left; font-size: var(--fs-3); font-weight: 700; color: var(--color-text); }}
.legend-ar {{ text-align: left; font-size: var(--fs-1); color: var(--color-text-muted); }}
.badge {{ display: inline-block; min-width: var(--space-5); padding: 0 var(--space-2); border-radius: var(--radius-1);
  color: var(--color-surface); font-size: var(--fs-1); font-weight: 700; line-height: var(--space-5); text-align: center; align-self: flex-start; }}
.line-val {{ font-size: var(--fs-6); font-weight: 700; color: var(--color-accent); font-variant-numeric: tabular-nums; line-height: 1.2; }}
.slider {{ width: 100%; height: var(--space-7); margin: var(--space-2) 0 0; accent-color: var(--color-accent); cursor: pointer; }}
.slider:focus-visible {{ outline: 2px solid var(--color-accent); outline-offset: var(--space-1); }}
.ends {{ display: flex; justify-content: space-between; font-size: var(--fs-1); color: var(--color-text-muted); }}
.rule {{ margin-top: var(--space-3); font-size: var(--fs-1); color: var(--color-text-muted); }}
.delta {{ margin-top: var(--space-3); font-size: var(--fs-3); font-weight: 700; color: var(--color-text); }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ font-size: var(--fs-1); font-weight: 700; color: var(--color-text-muted); text-align: left;
  padding: 0 var(--space-3) var(--space-3); border-bottom: 1px solid var(--color-border); white-space: nowrap; }}
th.num {{ text-align: right; }}
td {{ padding: var(--space-3); border-bottom: 1px solid var(--color-border); vertical-align: top; color: var(--color-text); }}
tr:last-child td {{ border-bottom: 0; }}
.t-name {{ font-weight: 700; }}
.t-sig {{ color: var(--color-text-muted); font-size: var(--fs-1); }}
.bcards {{ display: none; }}
.bcard {{ padding: var(--space-4) 0; border-bottom: 1px solid var(--color-border); }}
.bcard:last-child {{ border-bottom: 0; }}
.bcard-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }}
.bcard-name {{ font-size: var(--fs-3); font-weight: 700; color: var(--color-text); }}
.bcard-line {{ display: flex; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-1); color: var(--color-text); }}
.bcard-sig {{ margin-top: var(--space-2); font-size: var(--fs-1); color: var(--color-text-muted); }}
.reg-row {{ padding: var(--space-3) 0; }}
.reg-head {{ display: flex; justify-content: space-between; gap: var(--space-3); }}
.reg-name {{ font-weight: 700; color: var(--color-text); }}
.reg-amt {{ color: var(--color-text); }}
.reg-track {{ margin-top: var(--space-2); height: var(--space-4); background: var(--color-border); border-radius: var(--radius-1);
  overflow: hidden; }}
.reg-c {{ display: block; height: 100%; background: var(--grade-c); }}
.reg-sub {{ margin-top: var(--space-1); font-size: var(--fs-1); color: var(--color-text-muted); }}
.foot {{ margin-top: var(--space-6); font-size: var(--fs-1); color: var(--color-text-muted); }}
@media (max-width: {PHONE_MAX}px) {{
  .wrap {{ padding: var(--space-5) var(--space-4); }}
  .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); margin-top: var(--space-5); }}
  .kpi {{ padding: var(--space-3) var(--space-4); }}
  .kpi-num {{ font-size: var(--fs-5); }}
  .kpi-num.fs-down-1 {{ font-size: var(--fs-4); }}
  .kpi-num.fs-down-2 {{ font-size: var(--fs-3); }}
  .kpi-num.fs-down-3 {{ font-size: var(--fs-2); }}
  .row2 {{ grid-template-columns: minmax(0, 1fr); gap: var(--space-4); }}
  .card {{ padding: var(--space-4); }}
  .legend {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .tbl {{ display: none; }}
  .bcards {{ display: block; }}
}}
"""

JS = """
const DATA = JSON.parse(document.getElementById('board-data').textContent);
const G = ['S', 'A', 'B', 'C'];
const byId = Object.fromEntries(DATA.buyers.map(b => [b.id, b]));
const usd = n => '$' + Math.trunc(n).toLocaleString('en-US');
function gradeOf(p, line) {  // C부터 검사
  const t = line / 100;
  if (p >= t) return 'C';
  if (p >= t / 2) return 'B';
  if (p >= t / 4) return 'A';
  return 'S';
}
function stateOf(line) {
  const cnt = {S: 0, A: 0, B: 0, C: 0}, ar = {S: 0, A: 0, B: 0, C: 0}, regC = {}, g = {};
  for (const b of DATA.buyers) {
    const k = gradeOf(b.pd, line); g[b.id] = k; cnt[k] += 1; ar[k] += b.ar || 0;
    if (k === 'C') regC[b.region] = (regC[b.region] || 0) + (b.ar || 0);
  }
  return {cnt, ar, regC, g};
}
const BASE = stateOf(DATA.base);
const regTotal = {};
for (const b of DATA.buyers) regTotal[b.region] = (regTotal[b.region] || 0) + (b.ar || 0);
const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
function signed(n, fmt) { return (n < 0 ? '−' : '+') + fmt(Math.abs(n)); }
function fit() {  // 숫자가 칸보다 넓으면 글자를 한 단계씩 줄인다
  document.querySelectorAll('.fit').forEach(el => {
    el.classList.remove('fs-down-1', 'fs-down-2', 'fs-down-3');
    for (let i = 1; i <= 3 && el.scrollWidth > el.clientWidth; i++) {
      el.classList.remove('fs-down-' + (i - 1)); el.classList.add('fs-down-' + i);
    }
  });
}
function render(line) {
  const s = stateOf(line);
  set('line-val', line + '%');
  set('line-note', '위험 선 ' + line + '% 기준');
  set('k-c-n', s.cnt.C + '곳');
  set('k-c-n-sub', '위험 선 ' + line + '% 이상');
  set('k-c-ar', usd(s.ar.C));
  set('k-c-ar-sub', '전체 채권의 ' + (s.ar.C / DATA.total_ar * 100).toFixed(1) + '%');
  for (const k of G) {
    const seg = document.getElementById('seg-' + k);
    seg.style.width = (s.cnt[k] / DATA.buyers.length * 100).toFixed(4) + '%';
    seg.title = k + ' ' + s.cnt[k] + '곳';
    set('lg-n-' + k, s.cnt[k] + '곳');
    set('lg-ar-' + k, usd(s.ar[k]));
  }
  document.querySelectorAll('[data-gcell]').forEach(el => {
    const k = s.g[el.dataset.gcell];
    el.innerHTML = '<span class="badge g-' + k + '">' + k + '</span>';
  });
  DATA.regions.forEach((r, i) => {
    const c = s.regC[r] || 0;
    document.getElementById('rc-' + i).style.width = (regTotal[r] ? c / regTotal[r] * 100 : 0).toFixed(4) + '%';
    set('rc-amt-' + i, usd(c));
  });
  const dn = s.cnt.C - BASE.cnt.C, da = s.ar.C - BASE.ar.C;
  set('delta', '처음 ' + DATA.base + '%보다 C등급 ' + signed(dn, n => n + '곳') + ' · ' + signed(da, usd));
  fit();
}
const slider = document.getElementById('line');
slider.addEventListener('input', () => render(Number(slider.value)));
window.addEventListener('resize', fit);
render(Number(slider.value));
"""

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>바이어 리스크 한눈에</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main class="wrap">
  <header class="head">
    <h1>바이어 리스크 한눈에</h1>
    <p>기준일 <span class="num">{AS_OF}</span> · (가상) 한빛정밀(주) 바이어 {len(df)}곳 · 합성 데이터</p>
  </header>

  <section class="kpis" aria-label="핵심 숫자">{kpis}</section>

  <section class="row2">
    <article class="card">
      <div class="sec-head"><h2>신호등 등급 분포</h2><span class="sec-note" id="line-note">위험 선 {BASE_LINE}% 기준</span></div>
      <div class="gbar" role="img" aria-label="등급별 곳 수 막대">{seg}</div>
      <ul class="legend">{legend}</ul>
      <p class="rule">막대 길이는 곳 수, 아래 금액은 등급별 채권 합입니다.</p>
    </article>
    <article class="card">
      <div class="sec-head"><h2>위험 선</h2><span class="sec-note">회의에서 직접 움직여 보세요</span></div>
      <p class="line-val" id="line-val">{BASE_LINE}%</p>
      <input class="slider" id="line" type="range" min="{LINE_MIN}" max="{LINE_MAX}" step="1" value="{BASE_LINE}"
        aria-label="위험 선(%)">
      <div class="ends"><span>{LINE_MIN}%</span><span>{LINE_MAX}%</span></div>
      <p class="delta" id="delta">처음 {BASE_LINE}%보다 C등급 +0곳 · +$0</p>
      <p class="rule">위험 점수가 선 이상이면 C, 선의 절반 이상이면 B, 4분의 1 이상이면 A, 나머지는 S입니다.</p>
    </article>
  </section>

  <section class="card">
    <div class="sec-head"><h2>위험 상위 10</h2><span class="sec-note">위험 점수 높은 순 · 이번 주에 전화할 곳</span></div>
    <table class="tbl">
      <thead><tr><th>바이어</th><th>나라</th><th>등급</th><th class="num">위험 점수</th><th class="num">채권</th>
        <th class="num">연체</th><th>위험 신호</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <ul class="bcards">{''.join(cards)}</ul>
  </section>

  <section class="card">
    <div class="sec-head"><h2>지역별 채권</h2><span class="sec-note">큰 순서 · 빨간 부분이 지금 C등급인 채권</span></div>
    <ul>{reg}</ul>
  </section>

  <footer class="foot">(가상) 합성 데이터 · 기준일 {AS_OF} · 위험 점수는 판단을 돕는 값이고 결정은 사람이 합니다</footer>
</main>
<script type="application/json" id="board-data">{payload}</script>
<script>{JS}</script>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")

# ---------- 확인 출력 ----------
print(f"읽은 줄 {len(df)} · grade 열과 {BASE_LINE}% 규칙 일치 {match}/{len(df)}")
print("등급별 곳 수:", base["cnt"], "· 등급별 채권:", base["ar"])
print(f"C등급 채권 {usd(c_ar)} / 전체 채권 {usd(total_ar)} ({pct1(c_ar / total_ar * 100)})")
print(f"연체 {usd(overdue_sum)} · {overdue_n}곳")
print("지역별 채권(큰 순서):", [(r, v, base['region_c'].get(r, 0)) for r, v in region_rows])
print("위험 상위 10:", [(r.buyer_id, pct1(r.pd_30d * 100)) for r in top10.itertuples()])
s16 = state(16)
print(f"선 16% → C {s16['cnt']['C']}곳 · {usd(s16['ar']['C'])}")
print(f"페이지: {OUT.as_posix()}")
