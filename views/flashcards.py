import streamlit as st

from core import db, study
from views.common import get_index, run_ai


def render(user: dict, doc) -> None:
    st.subheader("🃏 핵심 용어 플래시카드")
    st.caption("용어를 보고 뜻을 떠올려 본 다음, 카드를 눌러 확인해요.")

    cards = db.get_flashcards(doc["id"])
    label = "🔄 카드 다시 만들기" if cards else "🚀 플래시카드 만들기"
    if st.button(label, type="primary"):
        result = run_ai(study.generate_flashcards, get_index(doc["id"]), spinner="핵심 용어를 정리하는 중...")
        if result:
            db.save_flashcards(doc["id"], result)
            cards = result

    if not cards:
        return
    st.markdown("---")
    cols = st.columns(2)
    for i, c in enumerate(cards):
        with cols[i % 2].expander(f"🃏 {c['term']}"):
            st.write(c["definition"])
