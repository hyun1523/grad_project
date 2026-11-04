import streamlit as st

from core import db, study
from views.common import run_ai


def render(user: dict, doc) -> None:
    st.subheader("📝 핵심 요약 노트")
    st.caption("문서 전체를 구간별로 요약한 뒤 하나로 합쳐요. 긴 문서도 끝까지 반영돼요.")

    saved = db.get_summary(doc["id"])
    label = "🔄 다시 요약하기" if saved else "🚀 AI 핵심 요약 생성하기"
    if st.button(label, type="primary"):
        bar = st.progress(0.0, text="요약 준비 중...")

        def progress(i, total, msg):
            bar.progress(i / total, text=f"{msg} ({i}/{total})")

        result = run_ai(study.summarize_document, _pages(doc["id"]), progress=progress, spinner="문서를 읽고 요약하는 중...")
        bar.empty()
        if result:
            db.save_summary(doc["id"], result)
            saved = result

    if saved:
        st.markdown("---")
        st.markdown(saved)
        st.download_button("📥 요약 노트 TXT 다운로드", saved, file_name=f"{doc['name']}_요약.txt", mime="text/plain")


def _pages(doc_id: int) -> list[str]:
    return [text for _, text in db.get_pages(doc_id)]
