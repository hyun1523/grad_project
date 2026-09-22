import os
import streamlit as st
import pdfplumber
from google import genai
from dotenv import load_dotenv

# .env 파일 로드 및 키 정제
load_dotenv()
raw_api_key = os.getenv("GEMINI_API_KEY")
API_KEY = raw_api_key.strip() if raw_api_key else ""

# 페이지 기본 설정
st.set_page_config(
    page_title="AI Study Partner",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS 적용 (디자인 스타일링)
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .main-header h1 {
        color: #60a5fa;
        margin-bottom: 0.5rem;
    }
    .stat-card {
        background-color: #f3f4f6;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #3b82f6;
        margin-bottom: 1rem;
        color: #111827;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown("""
    <div class="main-header">
        <h1>📚 AI Study Partner</h1>
        <p style="font-size: 1.1rem; color: #d1d5db;">
            대용량 PDF/전공 서적을 위한 스마트 AI 요약, Q&A 챗봇, 퀴즈 및 플래시카드 생성기
        </p>
    </div>
""", unsafe_allow_html=True)

# 사이드바 구성
with st.sidebar:
    st.image("https://img.icons8.com/isometric-folders/100/open-book.png", width=80)
    st.title("📌 시스템 정보")
    st.markdown("""
    **제작자:** 황병현  
    **엔진:** Google Gemini 2.5 Flash  
    **파서:** pdfplumber  
    """)
    st.markdown("---")
    st.subheader("💡 이용 가이드")
    st.markdown("""
    1. 메인 화면에 **PDF 파일**을 업로드합니다.
    2. 상단 **탭(Tab)**을 통해 원하는 AI 학습 도구를 선택합니다.
    3. 생성된 요약본 및 퀴즈는 **TXT 파일**로 소장할 수 있습니다.
    """)
    st.markdown("---")
    st.caption("© 2026 AI Study Partner. All rights reserved.")

# API 키 검증
if not API_KEY:
    st.error("🔑 `.env` 파일에 `GEMINI_API_KEY`가 설정되어 있지 않습니다.")
    st.stop()

# Gemini 클라이언트 초기화
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Gemini API 클라이언트 연결 실패: {e}")
    st.stop()

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 파일 업로드 섹션
uploaded_file = st.file_uploader("📂 분석할 PDF 문서를 올려주세요", type=["pdf"])

if uploaded_file is not None:
    # PDF 텍스트 추출 (pdfplumber 사용으로 한글 깨짐 방지)
    pdf_text = ""
    with st.spinner("📄 PDF 문서 텍스트 추출 중 (pdfplumber)..."):
        with pdfplumber.open(uploaded_file) as pdf:
            total_pages = len(pdf.pages)
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_text += extracted + "\n"
    
    # 상태 메세지 표시
    st.markdown(f"""
        <div class="stat-card">
            <strong>✅ 분석 완료!</strong> 총 <strong>{total_pages}</strong> 페이지, 약 <strong>{len(pdf_text):,}</strong> 글자의 텍스트를 정상적으로 추출했습니다.
        </div>
    """, unsafe_allow_html=True)

    # 4개 기능 탭
    tab1, tab2, tab3, tab4 = st.tabs(["📝 핵심 요약", "💬 AI 튜터 Q&A", "🧠 AI 퀴즈", "🃏 플래시카드"])

    # --- TAB 1: 핵심 요약 ---
    with tab1:
        st.subheader("📝 문서 핵심 요약 노트")
        st.caption("문서 전체 맥락을 바탕으로 주요 포인트를 체계적으로 정리합니다.")
        
        if st.button("🚀 AI 핵심 요약 생성하기", key="btn_summary"):
            with st.spinner("Gemini AI가 문서를 읽고 요약본을 작성하고 있습니다..."):
                try:
                    prompt = f"다음 문서의 내용을 바탕으로 핵심 내용을 3~5가지 항목으로 상세히 정리해줘:\n\n{pdf_text[:12000]}"
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    st.session_state.summary_result = response.text
                except Exception as e:
                    st.error(f"요약 생성 중 오류 발생: {e}")

        if "summary_result" in st.session_state:
            st.markdown("---")
            st.markdown(st.session_state.summary_result)
            st.download_button(
                label="📥 요약 노트 TXT 파일 다운로드",
                data=st.session_state.summary_result,
                file_name="AI_Study_Summary.txt",
                mime="text/plain"
            )

    # --- TAB 2: AI 튜터 Q&A ---
    with tab2:
        st.subheader("💬 AI 학습 튜터 대화방")
        st.caption("문서 내용 중 모르는 부분이나 이해가 안 되는 곳을 자유롭게 질문하세요.")

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_prompt := st.chat_input("질문을 입력해 주세요 (예: 이 논문의 핵심 결론이 뭐야?)"):
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("답변 작성 중..."):
                    try:
                        history_context = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
                        full_prompt = f"문서 내용:\n{pdf_text[:10000]}\n\n이전 대화 맥락:\n{history_context}\n\n사용자 질문: {user_prompt}\n\n위 내용을 바탕으로 친절하게 답변해줘."
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=full_prompt,
                        )
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"답변 생성 오류: {e}")

    # --- TAB 3: AI 퀴즈 ---
    with tab3:
        st.subheader("🧠 복습용 AI 퀴즈 생성기")
        st.caption("문서 내용을 얼마나 잘 이해했는지 테스트해 볼 수 있는 맞춤형 문제집을 생성합니다.")

        if st.button("🚀 AI 퀴즈 및 정답지 생성하기", key="btn_quiz"):
            with st.spinner("문서 기반 검증 퀴즈를 출제 중입니다..."):
                try:
                    prompt = f"다음 문서 내용을 기반으로 학습 확인용 퀴즈 3개(객관식/주관식 혼합)와 각 문제의 정답 및 상세 해설을 작성해줘:\n\n{pdf_text[:10000]}"
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    st.session_state.quiz_result = response.text
                except Exception as e:
                    st.error(f"퀴즈 생성 오류: {e}")

        if "quiz_result" in st.session_state:
            st.markdown("---")
            st.markdown(st.session_state.quiz_result)
            st.download_button(
                label="📥 퀴즈 및 정답지 TXT 다운로드",
                data=st.session_state.quiz_result,
                file_name="AI_Study_Quiz.txt",
                mime="text/plain"
            )

    # --- TAB 4: 플래시카드 ---
    with tab4:
        st.subheader("🃏 주요 개념 & 용어 플래시카드")
        st.caption("문서에 나오는 중요 전공 용어와 정의를 한눈에 모아봅니다.")

        if st.button("🚀 플래시카드 단어장 추출하기", key="btn_card"):
            with st.spinner("핵심 키워드를 정리하고 있습니다..."):
                try:
                    prompt = f"다음 문서에서 가장 중요한 주요 전문용어/개념 5가지를 뽑아서 '[용어/개념] - [상세 설명]' 형태의 단어장으로 깔끔하게 정돈해줘:\n\n{pdf_text[:10000]}"
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    st.session_state.cards_result = response.text
                except Exception as e:
                    st.error(f"플래시카드 생성 오류: {e}")

        if "cards_result" in st.session_state:
            st.markdown("---")
            st.markdown(st.session_state.cards_result)
else:
    # 파일이 업로드되지 않았을 때 보여주는 안내 카드
    st.info("👆 위 업로드 상자에 PDF 파일(전공 서적, 강의자료, 논문 등)을 등록해 주세요!")