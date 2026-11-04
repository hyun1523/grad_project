from collections import Counter

import streamlit as st

from core import db, study
from views.common import get_index, run_ai
from views.quiz import render_session, start_session


def render(user: dict, doc) -> None:
    st.subheader("📒 오답 노트")
    st.caption("가장 최근에 틀린 문제만 모아요. 다시 맞히면 자동으로 빠져요.")

    wrong = db.get_wrong_questions(user["id"], doc["id"])
    if not wrong:
        st.info("지금은 틀린 문제가 없어요. 퀴즈를 풀어보세요! 🎉")
        render_session(user, "review")
        return

    weak = Counter(w["topic"] for w in wrong if w["topic"])
    weak_topics = [t for t, _ in weak.most_common(3)]
    if weak_topics:
        st.markdown("**📉 약한 주제:** " + ", ".join(f"{t} ({c}개)" for t, c in weak.most_common(5)))

    col1, col2 = st.columns(2)
    if col1.button(f"🔁 틀린 문제 {len(wrong)}개 다시 풀기"):
        start_session("review", [w["id"] for w in wrong])
        st.rerun()
    if col2.button("🎯 약점 주제로 복습 퀴즈 새로 만들기", disabled=not weak_topics):
        questions = run_ai(
            study.generate_quiz,
            get_index(doc["id"]),
            n=5,
            topics=weak_topics,
            avoid=[w["question"] for w in wrong],
            spinner="약한 주제 중심으로 새 문제를 출제하는 중...",
        )
        if questions:
            start_session("review", db.add_questions(doc["id"], questions))
            st.rerun()

    render_session(user, "review")

    st.markdown("---")
    st.markdown(f"**틀린 문제 {len(wrong)}개**")
    for w in wrong:
        with st.expander(f"❌ {w['question']}  (틀린 횟수 {w['wrong_count']})"):
            st.markdown(f"내가 고른 답: {w['options'][w['last_selected']]}")
            st.markdown(f"정답: **{w['options'][w['answer_idx']]}**")
            if w["explanation"]:
                st.info(w["explanation"])
            meta = " · ".join(x for x in [f"주제: {w['topic']}" if w["topic"] else "", f"p.{w['page']}" if w["page"] else ""] if x)
            if meta:
                st.caption(meta)
