import streamlit as st

from core import db
from core.pdf import extract_pages


def render(user: dict, doc) -> None:
    st.subheader("📂 문서 관리")
    st.caption("PDF를 올리면 페이지별로 저장돼서 다음에 로그인해도 다시 쓸 수 있어요.")

    uploaded = st.file_uploader("분석할 PDF 문서를 올려주세요", type=["pdf"])
    if uploaded is not None and st.button("📥 문서 저장하고 분석 시작", type="primary"):
        try:
            with st.spinner("PDF 텍스트를 추출하는 중..."):
                pages = extract_pages(uploaded)
        except Exception as e:
            st.error(f"PDF를 읽지 못했어요. 손상되었거나 암호가 걸린 파일일 수 있어요. ({e})")
            return
        total_chars = sum(len(p) for p in pages)
        if total_chars == 0:
            st.error("텍스트를 찾지 못했어요. 스캔본(이미지) PDF는 아직 지원하지 않아요.")
            return
        doc_id = db.add_document(user["id"], uploaded.name, pages)
        st.session_state.current_doc_id = doc_id
        st.session_state.flash = f"✅ '{uploaded.name}' 저장 완료! {len(pages)}쪽, {total_chars:,}자를 추출했어요."
        st.rerun()

    st.markdown("---")
    docs = db.list_documents(user["id"])
    if not docs:
        st.info("아직 저장된 문서가 없어요. 위에서 PDF를 올려보세요.")
        return
    st.markdown("**내 문서 목록**")
    for d in docs:
        col1, col2, col3 = st.columns([5, 2, 1])
        mark = "👉 " if doc is not None and d["id"] == doc["id"] else ""
        col1.markdown(f"{mark}📄 **{d['name']}**")
        col2.caption(f"{d['total_pages']}쪽 · {d['created_at'][:10]}")
        if col3.button("🗑️", key=f"del_{d['id']}", help="문서 삭제"):
            db.delete_document(d["id"], user["id"])
            if st.session_state.get("current_doc_id") == d["id"]:
                st.session_state.pop("current_doc_id", None)
            st.rerun()
