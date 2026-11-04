import secrets

import streamlit as st

from core import db, study
from views.common import get_index, run_ai


def start_session(state_key: str, question_ids: list[int]) -> None:
    """퀴즈 한 판을 시작한다. nonce를 새로 만들어서 이전 판의 선택값이 남지 않게 한다."""
    st.session_state[state_key] = {
        "ids": question_ids,
        "submitted": False,
        "answers": {},
        "nonce": secrets.token_hex(4),
    }


def render_session(user: dict, state_key: str) -> None:
    """퀴즈를 풀고 채점 결과를 보여준다. 일반 퀴즈와 오답 복습이 함께 쓴다."""
    state = st.session_state.get(state_key)
    if not state:
        return
    questions = db.get_questions(state["ids"])
    if not questions:  # 문서를 지우는 등으로 문제가 사라진 경우
        st.session_state.pop(state_key, None)
        return
    prefix = f"{state_key}_{state['nonce']}"

    if not state["submitted"]:
        with st.form(f"form_{prefix}"):
            for i, q in enumerate(questions, start=1):
                st.markdown(f"**Q{i}. {q['question']}**")
                st.radio("보기", q["options"], index=None, key=f"{prefix}_{q['id']}", label_visibility="collapsed")
            submitted = st.form_submit_button("✅ 제출하고 채점하기", type="primary")
        if submitted:
            answers = {}
            for q in questions:
                choice = st.session_state.get(f"{prefix}_{q['id']}")
                answers[q["id"]] = q["options"].index(choice) if choice in q["options"] else None
            if any(v is None for v in answers.values()):
                st.warning("모든 문제에 답을 골라야 채점할 수 있어요.")
                return
            for q in questions:
                picked = answers[q["id"]]
                db.record_attempt(user["id"], q["id"], picked, picked == q["answer_idx"])
            state["answers"], state["submitted"] = answers, True
            st.rerun()
        return

    correct = sum(1 for q in questions if state["answers"][q["id"]] == q["answer_idx"])
    st.success(f"🎯 {len(questions)}문제 중 {correct}문제 정답! ({correct / len(questions):.0%})")
    for i, q in enumerate(questions, start=1):
        picked = state["answers"][q["id"]]
        ok = picked == q["answer_idx"]
        with st.expander(f"{'⭕' if ok else '❌'} Q{i}. {q['question']}", expanded=not ok):
            st.markdown(f"내 답: {q['options'][picked]}")
            if not ok:
                st.markdown(f"정답: **{q['options'][q['answer_idx']]}**")
            if q["explanation"]:
                st.info(q["explanation"])
            meta = " · ".join(x for x in [f"주제: {q['topic']}" if q["topic"] else "", f"p.{q['page']}" if q["page"] else ""] if x)
            if meta:
                st.caption(meta)
    if correct < len(questions):
        st.caption("틀린 문제는 '오답 노트' 메뉴에 자동으로 모였어요.")


def render(user: dict, doc) -> None:
    st.subheader("🧠 AI 퀴즈")
    st.caption("4지선다 문제를 직접 풀고 채점해요. 결과는 오답 노트와 학습 통계에 기록돼요.")

    col1, col2 = st.columns([3, 1])
    n = col1.slider("문제 수", 3, 10, 5)
    col2.write("")
    if col2.button("🚀 문제 만들기", type="primary"):
        recent = db.get_recent_question_texts(doc["id"])
        questions = run_ai(study.generate_quiz, get_index(doc["id"]), n=n, avoid=recent, spinner="문서 곳곳에서 문제를 출제하는 중...")
        if questions:
            ids = db.add_questions(doc["id"], questions)
            start_session("quiz", ids)
            st.rerun()

    render_session(user, "quiz")
