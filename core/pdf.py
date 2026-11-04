"""PDF에서 페이지별 텍스트를 추출한다 (pdfplumber: 한글 깨짐 방지)."""
import pdfplumber


def extract_pages(file) -> list[str]:
    """file: 경로 또는 파일 객체. 페이지 번호 순서대로 텍스트 리스트를 반환한다(빈 페이지는 '')."""
    pages: list[str] = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            pages.append((page.extract_text() or "").strip())
    return pages
