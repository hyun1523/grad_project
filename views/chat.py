import streamlit as st

from core import db, study
from views.common import get_index, run_ai


def _show(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["sources"]:
            st.caption("📖 참고한 페이지: " + ", ".join(f"p.{p}" for p in message["sources"]))


def render(user: dict, doc) -> None:
    st.subheader("💬 AI 튜터 Q&A")
    st.caption("질문과 관련된 부분만 문서에서 찾아 근거로 답하고, 참고한 페이지를 알려줘요. 대화는 저장돼요.")

    history = db.get_chats(doc["id"])
    if history and st.button("🧹 대화 기록 지우기"):
        db.clear_chats(doc["id"])
        st.rerun()
    for m in history:
        _show(m)

    question = st.chat_input("질문을 입력해 주세요 (예: 이 문서의 핵심 결론이 뭐야?)")
    if question:
        _show({"role": "user", "content": question, "sources": []})
        db.add_chat(doc["id"], "user", question)
        result = run_ai(study.answer_question, get_index(doc["id"]), history, question, spinner="답변 작성 중...")
        if result:
            answer, pages = result
            db.add_chat(doc["id"], "assistant", answer, pages)
            _show({"role": "assistant", "content": answer, "sources": pages})
