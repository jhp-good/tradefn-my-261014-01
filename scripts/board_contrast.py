"""3일차 실습 D — design.md 토큰의 글자 · 바탕 대비(WCAG 2.x 명암비)를 계산해 Markdown 표로 출력한다.

실행: uv run python scripts/board_contrast.py
기준: labs/day3/lab-d/lab_d_guide.md 「2. 디자인 주문서」 5번 — 모두 4.5 : 1 이상
TOKENS는 workbench/day3/outputs/design.md 토큰 표와 같은 값이어야 한다.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

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
}

# (글자, 바탕, 어디)
PAIRS = [
    ("color-text", "color-bg", "본문 글자 · 페이지 바탕"),
    ("color-text", "color-surface", "본문 글자 · 카드 면"),
    ("color-text-muted", "color-bg", "보조 글자 · 페이지 바탕"),
    ("color-text-muted", "color-surface", "보조 글자 · 카드 면"),
    ("color-accent", "color-surface", "강조 글자(링크 · 슬라이더 값) · 카드 면"),
    ("color-surface", "color-accent", "강조 단추 위 흰 글자"),
] + [
    (f"color-surface", f"grade-{g}", f"등급 {g.upper()} 라벨: 흰 글자 · 등급 색 바탕")
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
