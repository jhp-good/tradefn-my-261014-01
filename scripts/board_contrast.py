"""3일차 실습 D — design.md 토큰의 글자 · 바탕 대비(WCAG 2.x 명암비)를 계산해 Markdown 표로 출력한다.

실행: uv run python scripts/board_contrast.py
기준: labs/day3/lab-d/lab_d_guide.md 「2. 디자인 주문서」 5번 — 모두 4.5 : 1 이상
TOKENS는 workbench/day3/outputs/design.md 토큰 표와 같은 값이어야 한다.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

TOKENS = {
    "color-bg": "#181818",
    "color-surface": "#1F1F1F",
    "color-border": "#3C3C3C",
    "color-text": "#CCCCCC",
    "color-text-muted": "#9D9D9D",
    "color-accent": "#4DAAFC",
    "grade-s": "#73C991",
    "grade-a": "#B5C34A",
    "grade-b": "#E2A33E",
    "grade-c": "#F48771",
}

# (글자, 바탕, 어디)
PAIRS = [
    ("color-text", "color-bg", "본문 글자 · 페이지 바탕"),
    ("color-text", "color-surface", "본문 글자 · 카드 면"),
    ("color-text-muted", "color-bg", "보조 글자 · 페이지 바탕"),
    ("color-text-muted", "color-surface", "보조 글자 · 카드 면"),
    ("color-text", "color-surface", "KPI 숫자 · 카드 면"),
    ("color-text-muted", "color-surface", "표 머리 · 슬라이더 라벨(5% · 30%) · 카드 면"),
    ("color-text-muted", "color-bg", "바닥글 · 페이지 바탕"),
    ("color-accent", "color-surface", "강조 글자(슬라이더 값) · 카드 면"),
] + [
    (f"color-surface", f"grade-{g}", f"등급 {g.upper()} 라벨: 카드 면 색 글자 · 등급 색 바탕")
    for g in "sabc"
] + [
    (f"grade-{g}", "color-surface", f"등급 {g.upper()} 글자 · 카드 면") for g in "sabc"
] + [
    (f"grade-{g}", "color-bg", f"등급 {g.upper()} 글자 · 페이지 바탕") for g in "sabc"
]


def luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg, bg):
    hi, lo = sorted([luminance(fg), luminance(bg)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


print("| 어디 | 글자 | 바탕 | 대비 | 4.5 : 1 이상 |")
print("|---|---|---|---:|---|")
worst = None
for fg, bg, where in PAIRS:
    c = contrast(TOKENS[fg], TOKENS[bg])
    worst = c if worst is None else min(worst, c)
    print(f"| {where} | `{fg}` {TOKENS[fg]} | `{bg}` {TOKENS[bg]} | {c:.2f} | {'예' if c >= 4.5 else '아니오'} |")
print(f"\n가장 낮은 값: {worst:.2f}")
