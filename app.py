"""AI Study Partner - PDF 기반 AI 학습 보조 시스템 (진입점).

실행: python -m streamlit run app.py
"""
import os

import streamlit as st
from dotenv import load_dotenv

from core import db
from views import chat, documents, flashcards, login, quiz, stats, summary, wrong_notes

load_dotenv()

st.set_page_config(page_title="AI Study Partner", page_icon="📚", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        padding: 1.6rem 2rem; border-radius: 12px; color: white; margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .main-header h1 { color: #60a5fa; margin-bottom: 0.3rem; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
    <div class="main-header">
        <h1>📚 AI Study Partner</h1>
        <p style="font-size: 1.05rem; color: #d1d5db; margin: 0;">
            PDF 하나로 요약 · Q&A · 퀴즈 · 오답 노트 · 학습 통계까지, 나만의 AI 학습 파트너
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

db.init_db()

if not os.getenv("GEMINI_API_KEY", "").strip():
    st.error("🔑 `.env` 파일에 `GEMINI_API_KEY`가 설정되어 있지 않아요.")
    st.stop()

# ---------- 로그인 ----------
user = st.session_state.get("user")
if user is None:
    login.render()
    st.stop()

# ---------- 사이드바 ----------
MENUS = {
    "📂 문서 관리": documents,
    "📝 핵심 요약": summary,
    "💬 AI 튜터 Q&A": chat,
    "🧠 AI 퀴즈": quiz,
    "📒 오답 노트": wrong_notes,
    "🃏 플래시카드": flashcards,
    "📊 학습 통계": stats,
}
NEEDS_DOC = {"📝 핵심 요약", "💬 AI 튜터 Q&A", "🧠 AI 퀴즈", "📒 오답 노트", "🃏 플래시카드"}

with st.sidebar:
    st.markdown(f"### 👤 {user['username']}")
    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()
    st.markdown("---")

    docs = db.list_documents(user["id"])
    doc = None
    if docs:
        ids = [d["id"] for d in docs]
        current = st.session_state.get("current_doc_id")
        index = ids.index(current) if current in ids else 0
        names = {d["id"]: f"{d['name']} ({d['total_pages']}쪽)" for d in docs}
        chosen = st.selectbox("📄 학습할 문서", ids, index=index, format_func=names.get)
        st.session_state.current_doc_id = chosen
        doc = db.get_document(chosen, user["id"])
    else:
        st.caption("📄 저장된 문서가 없어요")

    menu = st.radio("메뉴", list(MENUS), label_visibility="collapsed")
    st.markdown("---")
    st.caption("엔진: Google Gemini 2.5 Flash · 파서: pdfplumber · DB: SQLite")
    st.caption("제작자: 황병현")

# 문서를 바꾸면 이전 문서의 퀴즈 진행 상태를 비운다
if st.session_state.get("_last_doc_id") != (doc["id"] if doc else None):
    st.session_state.pop("quiz", None)
    st.session_state.pop("review", None)
    st.session_state["_last_doc_id"] = doc["id"] if doc else None

# ---------- 본문 ----------
flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

if menu in NEEDS_DOC and doc is None:
    st.info("먼저 '📂 문서 관리'에서 PDF를 올려주세요.")
else:
    MENUS[menu].render(user, doc)
