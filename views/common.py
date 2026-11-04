"""화면들이 공유하는 도우미."""
import os

import streamlit as st

from core import db, rag
from core.llm import GeminiLLM, LLMError


@st.cache_resource
def get_llm() -> GeminiLLM:
    return GeminiLLM(os.getenv("GEMINI_API_KEY", "").strip())


@st.cache_resource(show_spinner=False)
def get_index(doc_id: int) -> rag.BM25Index:
    """문서별 검색 인덱스. 한 번 만들면 재사용해서 버튼을 누를 때마다 다시 계산하지 않는다."""
    pages = [text for _, text in db.get_pages(doc_id)]
    return rag.BM25Index(rag.chunk_pages(pages))


def run_ai(fn, *args, spinner: str = "AI가 작업 중이에요...", **kwargs):
    """AI 호출을 감싸서 오류를 화면에 친절하게 보여준다. 실패하면 None."""
    try:
        with st.spinner(spinner):
            return fn(get_llm(), *args, **kwargs)
    except LLMError as e:
        st.error(str(e))
    except Exception as e:  # 예상 못 한 오류도 앱이 죽지 않게 처리
        st.error(f"예상치 못한 오류가 발생했어요: {e}")
    return None
