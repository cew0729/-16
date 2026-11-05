
import re
from itertools import combinations

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# 페이지 설정
# --------------------------------------------------
st.set_page_config(
    page_title="급식 규칙 찾기",
    page_icon="🍱",
    layout="wide",
)

CSV_URL = (
    "https://raw.githubusercontent.com/it-teacher-go/"
    "data-share-/main/songtan_meals_184.csv"
)

st.title("🍱 급식 규칙 찾기")
st.caption("송탄고 중식 184일의 식단에서 메뉴 간 연관 규칙을 찾아봅니다.")

# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL, encoding="utf-8")

    required_columns = ["날짜", "식사", "메뉴"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(
            f"CSV에 필요한 열이 없습니다: {', '.join(missing)}"
        )

    df = df[required_columns].copy()
    df = df[df["메뉴"].notna()].copy()

    # 메뉴 이름에서 괄호와 괄호 안 내용을 제거
    def clean_menu(menu):
        menu = str(menu).strip()
        menu = re.sub(r"\([^()]*\)", "", menu)
        menu = re.sub(r"\s+", " ", menu).strip()
        return menu

    baskets = []

    for menu_text in df["메뉴"]:
        menus = [
            clean_menu(item)
            for item in str(menu_text).split("|")
        ]

        # 빈 메뉴 제거, 같은 식단 안 중복 메뉴 제거
        menus = sorted(set(menu for menu in menus if menu))

        baskets.append(menus)

    df["메뉴목록"] = baskets

    # 분석 가능한 메뉴가 있는 식단만 사용
    df = df[df["메뉴목록"].map(len) > 0].reset_index(drop=True)

    return df


try:
    df = load_data()
except Exception as e:
    st.error(f"CSV 데이터를 불러오지 못했습니다: {e}")
    st.stop()

# --------------------------------------------------
# 메뉴 쌍과 연관 규칙 분석
# --------------------------------------------------
total_days = len(df)

menu_counts = {}
pair_counts = {}

for menus in df["메뉴목록"]:
    for menu in menus:
        menu_counts[menu] = menu_counts.get(menu, 0) + 1

    for a, b in combinations(menus, 2):
        pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

total_menu_types = len(menu_counts)
total_pairs = len(pair_counts)

rules = []

for (a, b), together in pair_counts.items():
    support = together / total_days
    confidence_ab = together / menu_counts[a]
    confidence_ba = together / menu_counts[b]

    # 향상도 = 신뢰도 / 결과 메뉴의 지지도
    lift_ab = confidence_ab / (menu_counts[b] / total_days)
    lift_ba = confidence_ba / (menu_counts[a] / total_days)

    rules.append({
        "조건": a,
        "결과": b,
        "동시": together,
        "지지도": support,
        "신뢰도": confidence_ab,
        "향상도": lift_ab,
    })

    rules.append({
        "조건": b,
        "결과": a,
        "동시": together,
        "지지도": support,
        "신뢰도": confidence_ba,
        "향상도": lift_ba,
    })

rules_df = pd.DataFrame(rules)

# --------------------------------------------------
# 요약 정보
# --------------------------------------------------
m1, m2, m3 = st.columns(3)
m1.metric("급식 일수", f"{total_days}일")
m2.metric("메뉴 종류 수", f"{total_menu_types}종")
m3.metric("함께 나온 메뉴 쌍 수", f"{total_pairs}쌍")

st.divider()

# --------------------------------------------------
# 필터와 정렬
# --------------------------------------------------
all_menus = sorted(menu_counts.keys())

selected_menu = st.selectbox(
    "메뉴 선택 (전체 규칙을 보려면 전체 메뉴)",
    ["전체 메뉴"] + all_menus,
)

sort_by = st.selectbox(
    "정렬 기준",
    ["향상도 순", "신뢰도 순", "동시 순"],
)

sort_column = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시",
}[sort_by]

filtered_rules = rules_df.copy()

if selected_menu != "전체 메뉴":
    filtered_rules = filtered_rules[
        (filtered_rules["조건"] == selected_menu)
        | (filtered_rules["결과"] == selected_menu)
    ]

filtered_rules = filtered_rules.sort_values(
    by=[sort_column, "신뢰도", "동시"],
    ascending=[False, False, False],
).reset_index(drop=True)

# --------------------------------------------------
# 규칙 표
# --------------------------------------------------
st.subheader("메뉴 연관 규칙")

display_rules = filtered_rules.copy()
display_rules["지지도"] = display_rules["지지도"].map(
    lambda x: f"{x:.3f}"
)
display_rules["신뢰도"] = display_rules["신뢰도"].map(
    lambda x: f"{x:.3f}"
)
display_rules["향상도"] = display_rules["향상도"].map(
    lambda x: f"{x:.3f}"
)

st.dataframe(
    display_rules[
        ["조건", "결과", "동시", "지지도", "신뢰도", "향상도"]
    ],
    hide_index=True,
    width="stretch",
)

# --------------------------------------------------
# 향상도 상위 10개 그래프
# --------------------------------------------------
st.subheader("향상도 상위 10개 규칙")

top_rules = filtered_rules.sort_values(
    by=["향상도", "신뢰도", "동시"],
    ascending=[False, False, False],
).head(10).copy()

if top_rules.empty:
    st.info("선택한 메뉴에 해당하는 규칙이 없습니다.")
else:
    top_rules["규칙"] = (
        top_rules["조건"] + " → " + top_rules["결과"]
    )

    fig = px.bar(
        top_rules.sort_values("향상도", ascending=True),
        x="향상도",
        y="규칙",
        orientation="h",
        text=top_rules.sort_values(
            "향상도", ascending=True
        )["향상도"].map(lambda x: f"{x:.2f}"),
        color="향상도",
        color_continuous_scale="Blues",
        title="향상도 상위 10개 연관 규칙",
    )

    fig.update_layout(
        xaxis_title="향상도",
        yaxis_title="",
        coloraxis_showscale=False,
    )

    st.plotly_chart(fig, width="stretch")
