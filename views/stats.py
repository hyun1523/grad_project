import pandas as pd
import streamlit as st

from core import db

WEAK_THRESHOLD = 0.6  # 정답률이 이 값보다 낮은 주제를 약점으로 본다


def render(user: dict, doc) -> None:
    st.subheader("📊 학습 통계")
    s = db.get_stats(user["id"])

    c1, c2, c3 = st.columns(3)
    c1.metric("저장한 문서", s["doc_count"])
    c2.metric("푼 문제", s["total"])
    c3.metric("전체 정답률", f"{s['correct'] / s['total']:.0%}" if s["total"] else "-")

    if not s["total"]:
        st.info("아직 푼 문제가 없어요. 퀴즈를 풀면 통계가 쌓여요.")
        return

    st.markdown("#### 📅 날짜별 학습량")
    daily = pd.DataFrame(s["daily"]).set_index("day").rename(columns={"solved": "푼 문제", "correct": "맞힌 문제"})
    st.bar_chart(daily[["푼 문제", "맞힌 문제"]])

    if s["topics"]:
        st.markdown("#### 🧩 주제별 정답률")
        topics = pd.DataFrame(s["topics"])
        topics["정답률"] = topics["correct"] / topics["solved"] * 100
        st.bar_chart(topics.set_index("topic")[["정답률"]])

        weak = topics[topics["정답률"] < WEAK_THRESHOLD * 100].sort_values("정답률")
        if len(weak):
            st.warning("📉 복습이 필요한 주제: " + ", ".join(f"{r.topic} ({r.정답률:.0f}%)" for r in weak.itertuples()))
        else:
            st.success("모든 주제에서 정답률이 60% 이상이에요. 잘하고 있어요! 👍")

    st.markdown("#### 📄 문서별 현황")
    docs = pd.DataFrame(s["docs"]).rename(columns={"name": "문서", "solved": "푼 문제", "correct": "맞힌 문제"})
    st.dataframe(docs, use_container_width=True, hide_index=True)
