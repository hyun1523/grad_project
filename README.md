# 📚 AI Study Partner (PDF 기반 AI 학습 보조 시스템)

> 대용량 PDF 문서 및 학술 논문을 위한 **Google Gemini 2.5 Flash LLM** 기반 자동 요약, Q&A, 퀴즈 및 플래시카드 생성 웹 서비스입니다.

---

## 🌟 주요 기능

- **한글 파싱 특화**: `pdfplumber` 라이브러리를 적용하여 한글 글자 깨짐 현상 차단
- **스마트 핵심 요약**: 문서 전체 맥락을 파악해 3~5가지 핵심 항목으로 요약 및 TXT 다운로드 제공
- **연속 대화 AI 튜터**: 대화 세션 맥락을 기억하는 맞춤형 Q&A 챗봇
- **자동 퀴즈 & 해설**: 학습 확인을 위한 객관식/주관식 테스트 문제 자동 출제
- **핵심 용어 단어장**: 전공 용어 및 핵심 개념 플래시카드 자동 추출

---

## 🛠️ Tech Stack

- **Language**: Python 3.14
- **UI Framework**: Streamlit
- **AI Model**: Google Gemini 2.5 Flash (`google-genai` SDK)
- **PDF Parser**: `pdfplumber`
- **Environment**: `python-dotenv`

---

## 🚀 실행 방법

### 1. 레포지토리 클론 및 이동
```bash
git clone https://github.com/hyun1523/grad_project.git
cd grad_project

### 2. 필수 라이브러리 설치
```bash
pip install streamlit google-genai pdfplumber python-dotenv

### 3. 환경변수 .env 설정
```bash
GEMINI_API_KEY=your_gemini_api_key_here

### 4. 앱 실행
```bash
python -m streamlit run app.py
