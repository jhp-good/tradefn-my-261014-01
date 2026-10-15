"""2일차 실습 A 검증 — scripts/clean_buyers.py가 만든 d2_buyers_clean.csv를 검사한다.

실행: uv run pytest -q   (저장소 맨 위에서, pytest.ini가 workbench/를 찾는다)
근거: workbench/day2/rules/정제규칙.md 1–7칸
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
CLEAN = ROOT / "workbench/day2/outputs/d2_buyers_clean.csv"


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(CLEAN)


def test_row_count(df):
    assert len(df) == 150


def test_buyer_id_unique(df):
    assert df["buyer_id"].notna().all()
    assert df["buyer_id"].is_unique


def test_currency_four_kinds(df):
    # 규칙 1칸: 9가지 표기 → USD · EUR · JPY · CNY
    assert set(df["ccy_clean"]) == {"USD", "EUR", "JPY", "CNY"}


@pytest.mark.parametrize("col", ["amt_num", "ar_balance_usd"])
def test_amount_non_negative(df, col):
    # 규칙 2칸: 모든 금액이 숫자로 바뀌었고(빈칸 없음) 음수가 없다
    assert df[col].notna().all(), df.loc[df[col].isna(), "buyer_id"].tolist()
    assert (df[col] >= 0).all(), df.loc[df[col] < 0, "buyer_id"].tolist()


def test_unit_flag_b072(df):
    # 규칙 4칸: USD 잔액 > 한도 × 10 → unit_flag = 1, ÷1,000. 진단상 해당은 B072 한 곳
    flagged = df.loc[df["unit_flag"] == 1, "buyer_id"].tolist()
    assert flagged == ["B072"]
    b072 = df.set_index("buyer_id").loc["B072"]
    assert b072["amt_num"] == pytest.approx(8320)  # 원천 8,320,000 ÷ 1,000 = 구간 합 8,320
    assert b072["ar_balance_usd"] == pytest.approx(9665.37, abs=0.01)
