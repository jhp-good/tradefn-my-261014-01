"""2일차 실습 B — 뉴스 채점 결과(news_scored.jsonl) 검사. 읽기만 하고 고치지 않는다.

근거: workbench/day2/prompts/news_score_v1.md ([척도] · [규칙] 2 · 5 · [출력])
실행: uv run python scripts/validate_scores.py
입력: workbench/day2/outputs/news_scored.jsonl · data/checkpoints/d2_news.csv(원문, 읽기만)
결과: 화면 출력만. 위반 행이 있으면 종료 코드 1

검사
  C1 줄 수     JSONL이 100줄(d2_news.csv 1–100행 채점분)
  C2 점수      news_sent_0_10이 0–10 정수(bool 제외)
  C3 라벨      점수 대역과 맞는지 — 0–2 severe, 3–4 high, 5 watch, 6–10 low
  C4 근거      evidence가 같은 news_id 원문의 headline 또는 body_short 안에 글자 그대로 있는지
"""
import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SCORED = Path("workbench/day2/outputs/news_scored.jsonl")
NEWS = Path("data/checkpoints/d2_news.csv")
N_EXPECTED = 100


def band(score):
    if score <= 2:
        return "severe"
    if score <= 4:
        return "high"
    if score == 5:
        return "watch"
    return "low"


news = {r["news_id"]: r for r in csv.DictReader(NEWS.open(encoding="utf-8-sig"))}
lines = [l for l in SCORED.read_text(encoding="utf-8").splitlines() if l.strip()]

bad = []  # (줄 번호, news_id, 검사, 내용)
if len(lines) != N_EXPECTED:
    bad.append((0, "-", "C1 줄 수", f"{len(lines)}줄 (기대 {N_EXPECTED})"))

for no, line in enumerate(lines, 1):
    try:
        o = json.loads(line)
    except json.JSONDecodeError as e:
        bad.append((no, "-", "JSON", str(e)))
        continue
    nid = o.get("news_id", "-")
    s = o.get("news_sent_0_10")
    score_ok = isinstance(s, int) and not isinstance(s, bool) and 0 <= s <= 10
    if not score_ok:
        bad.append((no, nid, "C2 점수", repr(s)))
    elif o.get("label") != band(s):
        bad.append((no, nid, "C3 라벨", f"점수 {s} → {band(s)}인데 {o.get('label')!r}"))
    src = news.get(nid)
    ev = o.get("evidence", "")
    if src is None:
        bad.append((no, nid, "C4 근거", "원문에 없는 news_id"))
    elif not ev or (ev not in src["headline"] and ev not in src["body_short"]):
        bad.append((no, nid, "C4 근거", f"원문에 그대로 없음: {ev!r}"))

print(f"검사 대상: {SCORED} ({len(lines)}줄)")
if not bad:
    print("위반 0건 — C1 줄 수 · C2 점수 · C3 라벨 · C4 근거 모두 통과")
    sys.exit(0)

print(f"위반 {len(bad)}건")
print("| 줄 | news_id | 검사 | 내용 |")
print("|---|---|---|---|")
for no, nid, chk, msg in bad:
    print(f"| {no} | {nid} | {chk} | {msg} |")
sys.exit(1)
