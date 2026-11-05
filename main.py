
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
st.caption("송탄고 중식 식단에서 메뉴 간 연관 규칙을 찾아봅니다.")


# --------------------------------------------------
# 데이터 불러오기 및 전처리
# --------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL, encoding="utf-8")

    required_columns = ["날짜", "식사", "메뉴"]
    missing_columns = [
        col for col in required_columns if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"CSV에 필요한 열이 없습니다: {', '.join(missing_columns)}"
        )

    df = df[required_columns].copy()
    df = df.dropna(subset=["메뉴"])

    def clean_menu(menu):
        menu = str(menu).strip()

        # 괄호와 괄호 안의 내용 제거
        menu = re.sub(r"\([^()]*\)", "", menu)
        menu = re.sub(r"（[^（）]*）", "", menu)

        # 중첩 괄호도 반복해서 제거
        previous = None
        while previous != menu:
            previous = menu
            menu = re.sub(r"\([^()]*\)", "", menu)
            menu = re.sub(r"（[^（）]*）", "", menu)

        return re.sub(r"\s+", " ", menu).strip()

    baskets = []

    for menu_text in df["메뉴"]:
        menus = [
            clean_menu(item)
            for item in str(menu_text).split("|")
        ]

        # 빈 메뉴 제거 및 하루 안의 중복 메뉴 제거
        menus = sorted(set(menu for menu in menus if menu))
        baskets.append(menus)

    df["메뉴목록"] = baskets

    # 메뉴가 하나 이상 있는 식단만 분석
    df = df[df["메뉴목록"].map(len) > 0].reset_index(drop=True)

    return df


try:
    df = load_data()
except Exception as e:
    st.error(f"CSV 데이터를 불러오지 못했습니다: {e}")
    st.stop()


# --------------------------------------------------
# 메뉴 출현 횟수와 메뉴 쌍 출현 횟수 계산
# --------------------------------------------------
total_days = len(df)

menu_counts = {}
pair_counts = {}

for menus in df["메뉴목록"]:
    for menu in menus:
        menu_counts[menu] = menu_counts.get(menu, 0) + 1

    for a, b in combinations(menus, 2):
        pair = tuple(sorted((a, b)))
        pair_counts[pair] = pair_counts.get(pair, 0) + 1

total_menu_types = len(menu_counts)
total_pairs = len(pair_counts)


# --------------------------------------------------
# 연관 규칙 생성
# --------------------------------------------------
rules = []

for (a, b), together in pair_counts.items():

    # 지지도 = 함께 나온 날짜 수 / 전체 급식 일수
    support = together / total_days

    # A → B
    confidence_ab = together / menu_counts[a]
    lift_ab = confidence_ab / (menu_counts[b] / total_days)

    rules.append({
        "조건": a,
        "결과": b,
        "동시": together,
        "지지도": support,
        "신뢰도": confidence_ab,
        "향상도": lift_ab,
    })

    # B → A
    confidence_ba = together / menu_counts[b]
    lift_ba = confidence_ba / (menu_counts[a] / total_days)

    rules.append({
        "조건": b,
        "결과": a,
        "동시": together,
        "지지도": support,
        "신뢰도": confidence_ba,
        "향상도": lift_ba,
    })

rules_df = pd.DataFrame(
    rules,
    columns=["조건", "결과", "동시", "지지도", "신뢰도", "향상도"],
)


# --------------------------------------------------
# 요약 정보
# --------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("급식 일수", f"{total_days}일")
col2.metric("메뉴 종류 수", f"{total_menu_types}종")
col3.metric("함께 나온 메뉴 쌍 수", f"{total_pairs}쌍")

st.divider()


# --------------------------------------------------
# 최소 동시 일수 슬라이더
# --------------------------------------------------
min_together = st.slider(
    "최소 동시 일수",
    min_value=1,
    max_value=10,
    value=1,
    step=1,
    help="선택한 일수보다 적게 함께 나온 규칙은 제외합니다.",
)


# --------------------------------------------------
# 메뉴 선택 및 정렬
# --------------------------------------------------
all_menus = sorted(menu_counts.keys())

selected_menu = st.selectbox(
    "연관 규칙 좁혀 보기",
    ["전체 메뉴"] + all_menus,
    key="association_menu_select",
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


# --------------------------------------------------
# 규칙 필터링 및 정렬
# --------------------------------------------------
filtered_rules = rules_df[
    rules_df["동시"] >= min_together
].copy()

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

st.write(f"현재 조건에 해당하는 규칙: **{len(filtered_rules):,}개**")

if filtered_rules.empty:
    st.info("선택한 조건에 해당하는 규칙이 없습니다.")
else:
    display_rules = filtered_rules.copy()

    # 지지도와 신뢰도는 퍼센트, 향상도는 배수로 표시
    display_rules["지지도"] = (
        display_rules["지지도"] * 100
    ).round(1).map(lambda x: f"{x:.1f}%")

    display_rules["신뢰도"] = (
        display_rules["신뢰도"] * 100
    ).round(1).map(lambda x: f"{x:.1f}%")

    display_rules["향상도"] = (
        display_rules["향상도"]
    ).round(3).map(lambda x: f"{x:.3f}")

    st.dataframe(
        display_rules[
            ["조건", "결과", "동시", "지지도", "신뢰도", "향상도"]
        ],
        hide_index=True,
        width="stretch",
    )


# --------------------------------------------------
# 향상도 상위 10개 가로 막대그래프
# --------------------------------------------------
st.subheader("향상도 상위 10개 규칙")

top_rules = (
    filtered_rules
    .sort_values(
        by=["향상도", "신뢰도", "동시"],
        ascending=[False, False, False],
    )
    .head(10)
    .copy()
)

if top_rules.empty:
    st.info("그래프로 표시할 규칙이 없습니다.")
else:
    top_rules["규칙"] = (
        top_rules["조건"] + " → " + top_rules["결과"]
    )

    chart_df = top_rules.sort_values(
        "향상도",
        ascending=True,
    ).copy()

    chart_df["향상도표시"] = chart_df["향상도"].round(3)

    fig = px.bar(
        chart_df,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도표시",
        color="향상도",
        color_continuous_scale="Blues",
        hover_data={
            "조건": True,
            "결과": True,
            "동시": True,
            "지지도": ":.3%",
            "신뢰도": ":.3%",
            "향상도": ":.3f",
            "규칙": False,
            "향상도표시": False,
        },
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
    )

    fig.update_layout(
        xaxis_title="향상도",
        yaxis_title="",
        coloraxis_showscale=False,
        height=max(400, len(chart_df) * 45),
        margin=dict(l=20, r=70, t=30, b=20),
    )

    st.plotly_chart(fig, width="stretch")


# --------------------------------------------------
# 함께 나온 적 없는 짝
# --------------------------------------------------
st.divider()
st.subheader("함께 나온 적 없는 짝")

st.write(
    "선택한 메뉴와 같은 날 한 번도 함께 나오지 않았지만, "
    "혼자서는 10일 이상 나온 메뉴를 출현 횟수 순으로 보여 줍니다."
)

selected_menu_absent = st.selectbox(
    "함께 나온 적 없는 짝을 찾을 메뉴",
    all_menus,
    key="absent_menu_select",
)

selected_menu_days = menu_counts[selected_menu_absent]

st.write(
    f"**{selected_menu_absent}** 메뉴가 나온 날: "
    f"**{selected_menu_days}일**"
)

absent_candidates = []

for candidate, candidate_days in menu_counts.items():

    # 선택한 메뉴 자신은 제외
    if candidate == selected_menu_absent:
        continue

    # 혼자서 10일 이상 나온 메뉴만 포함
    if candidate_days < 10:
        continue

    pair = tuple(sorted((selected_menu_absent, candidate)))

    # 두 메뉴가 한 번도 함께 나오지 않은 경우
    if pair not in pair_counts:
        absent_candidates.append({
            "메뉴": candidate,
            "출현 일수": candidate_days,
        })

absent_df = pd.DataFrame(
    absent_candidates,
    columns=["메뉴", "출현 일수"],
)

if absent_df.empty:
    st.info("조건에 맞는 메뉴가 없습니다.")
else:
    absent_df = absent_df.sort_values(
        by=["출현 일수", "메뉴"],
        ascending=[False, True],
    ).reset_index(drop=True)

    st.dataframe(
        absent_df,
        hide_index=True,
        width="stretch",
    )
