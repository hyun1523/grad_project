"""학습 기능(요약, Q&A, 퀴즈, 플래시카드)의 프롬프트와 후처리.

llm 인자는 text(prompt) -> str, json(prompt) -> object 두 메서드만 있으면 된다.
"""
import random

from core.llm import LLMError
from core.rag import BM25Index, Chunk, group_for_summary, sample_evenly

MAX_SUMMARY_GROUPS = 12  # 긴 문서도 AI 호출 횟수가 무한정 늘지 않게 상한을 둔다
NUM_OPTIONS = 4


# ---------------------------------------------------------------- 요약
def summarize_document(llm, pages: list[str], progress=None) -> str:
    """문서 전체를 구간별로 요약한 뒤(Map) 하나로 합친다(Reduce)."""
    total_chars = sum(len(p) for p in pages)
    if total_chars == 0:
        raise LLMError("문서에서 텍스트를 찾지 못했어요. 스캔본(이미지) PDF는 아직 지원하지 않아요.")
    max_chars = max(9000, total_chars // MAX_SUMMARY_GROUPS + 1)
    groups = group_for_summary(pages, max_chars=max_chars)

    if len(groups) == 1:
        _, _, text = groups[0]
        return llm.text(
            "다음 문서의 핵심 내용을 학습용 노트로 정리해줘. "
            "큰 주제별로 소제목을 달고, 각 주제는 불릿으로 핵심 개념과 정의를 담아줘. "
            "마지막에 '꼭 기억할 점' 3가지를 덧붙여줘. 한국어로 작성해.\n\n" + text
        )

    partials = []
    for i, (start, end, text) in enumerate(groups, start=1):
        if progress:
            progress(i, len(groups) + 1, f"{start}~{end}쪽 요약 중")
        partials.append(
            f"### {start}~{end}쪽\n"
            + llm.text(
                f"다음은 문서의 {start}~{end}쪽 부분이야. 이 부분의 핵심 개념과 내용을 "
                "불릿 5~8개로 간결하게 정리해줘. 한국어로 작성해.\n\n" + text
            )
        )
    if progress:
        progress(len(groups) + 1, len(groups) + 1, "전체 요약 합치는 중")
    return llm.text(
        "아래는 한 문서를 구간별로 요약한 내용이야. 이를 하나의 학습 노트로 합쳐줘. "
        "큰 주제별로 소제목을 달고 중복은 제거하되, 각 항목 끝에 관련 쪽수를 (p.12) 형태로 남겨줘. "
        "마지막에 '꼭 기억할 점' 5가지를 덧붙여줘. 한국어로 작성해.\n\n" + "\n\n".join(partials)
    )


# ---------------------------------------------------------------- Q&A
def answer_question(llm, index: BM25Index, history: list[dict], question: str, top_k: int = 5):
    """질문과 관련된 부분만 검색해서 근거로 쓰고, 참고한 페이지를 함께 돌려준다."""
    hits = index.search(question, top_k=top_k)
    if not hits:
        return "문서에서 이 질문과 관련된 내용을 찾지 못했어요. 질문을 다른 표현으로 바꿔서 다시 물어봐 주세요.", []
    context = "\n\n".join(f"[p.{c.page}]\n{c.text}" for c in hits)
    recent = "\n".join(
        f"{'학생' if m['role'] == 'user' else '튜터'}: {m['content']}" for m in history[-6:]
    )
    prompt = (
        "너는 친절한 학습 튜터야. 아래 '문서 발췌'만 근거로 학생의 질문에 답해줘.\n"
        "- 발췌에 없는 내용은 추측하지 말고 '문서에서 확인되지 않는다'고 말해줘.\n"
        "- 답변 중 근거가 된 부분 끝에 (p.쪽수) 형태로 쪽수를 표시해줘.\n"
        "- 한국어로, 이해하기 쉽게 설명해줘.\n\n"
        f"[문서 발췌]\n{context}\n\n[이전 대화]\n{recent or '(없음)'}\n\n[학생 질문]\n{question}"
    )
    answer = llm.text(prompt)
    pages = sorted({c.page for c in hits})
    return answer, pages


# ---------------------------------------------------------------- 퀴즈
def validate_questions(raw, rng: random.Random | None = None) -> list[dict]:
    """AI가 만든 문제를 검증하고 정리한다. 잘못된 항목은 버린다.
    AI는 정답을 특정 번호에 몰아두는 경향이 있어서, 보기를 섞고 정답 번호를 다시 계산한다."""
    rng = rng or random.Random()
    if isinstance(raw, dict):
        raw = raw.get("questions", [])
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        try:
            question = str(item["question"]).strip()
            options = [str(o).strip() for o in item["options"]]
            answer_idx = int(item["answer_idx"])
        except (KeyError, TypeError, ValueError):
            continue
        if not question or len(options) != NUM_OPTIONS or len(set(options)) != NUM_OPTIONS:
            continue
        if not all(options) or not 0 <= answer_idx < NUM_OPTIONS:
            continue
        order = list(range(NUM_OPTIONS))
        rng.shuffle(order)
        shuffled = [options[i] for i in order]
        page = item.get("page")
        result.append(
            {
                "question": question,
                "options": shuffled,
                "answer_idx": order.index(answer_idx),
                "explanation": str(item.get("explanation", "")).strip(),
                "topic": str(item.get("topic", "")).strip()[:40],
                "page": int(page) if isinstance(page, (int, float)) or str(page).isdigit() else None,
            }
        )
    return result


_QUIZ_FORMAT = (
    '반드시 아래 JSON 형식으로만 출력해:\n'
    '{"questions": [{"question": "문제", "options": ["보기1", "보기2", "보기3", "보기4"], '
    '"answer_idx": 0, "explanation": "정답 해설", "topic": "짧은 주제어", "page": 12}]}\n'
    "- options는 정확히 4개, answer_idx는 정답의 위치(0~3)\n"
    "- page는 근거가 된 쪽수(발췌 앞의 [p.N] 참고)\n"
    "- topic은 10자 안팎의 핵심 개념 이름\n"
    "- 단순 암기보다 이해를 확인하는 문제를 섞고, 오답 보기도 그럴듯하게 만들어줘\n"
)


def generate_quiz(
    llm,
    index: BM25Index,
    n: int = 5,
    topics: list[str] | None = None,
    avoid: list[str] | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """topics가 있으면 그 주제와 관련된 부분에서(약점 복습), 없으면 문서 곳곳에서 문제를 낸다."""
    rng = rng or random.Random()
    if topics:
        picked: list[Chunk] = []
        for t in topics:
            picked.extend(index.search(t, top_k=2))
        seen, chunks = set(), []
        for c in picked:
            if (c.page, c.text[:30]) not in seen:
                seen.add((c.page, c.text[:30]))
                chunks.append(c)
        focus = "특히 다음 주제를 중심으로 출제해: " + ", ".join(topics) + "\n"
    else:
        pool = index.chunks
        chunks = sorted(rng.sample(pool, min(6, len(pool))), key=lambda c: c.page)
        focus = ""
    if not chunks:
        raise LLMError("문제를 낼 만한 텍스트가 부족해요.")
    context = "\n\n".join(f"[p.{c.page}]\n{c.text}" for c in chunks)[:9000]
    avoid_text = ""
    if avoid:
        avoid_text = "다음 문제와 겹치지 않게 새로운 문제를 내줘:\n- " + "\n- ".join(a[:80] for a in avoid[-15:]) + "\n"
    prompt = (
        f"아래 문서 발췌를 바탕으로 4지선다 객관식 문제 {n}개를 만들어줘.\n{focus}{avoid_text}\n"
        f"{_QUIZ_FORMAT}\n[문서 발췌]\n{context}"
    )
    questions = validate_questions(llm.json(prompt), rng)
    if not questions:
        raise LLMError("퀴즈를 만들지 못했어요. 다시 시도해 주세요.")
    return questions[:n]


# ---------------------------------------------------------------- 플래시카드
def generate_flashcards(llm, index: BM25Index, n: int = 10) -> list[dict]:
    chunks = sample_evenly(index.chunks, 8)
    if not chunks:
        raise LLMError("플래시카드를 만들 텍스트가 부족해요.")
    context = "\n\n".join(f"[p.{c.page}]\n{c.text}" for c in chunks)[:9000]
    prompt = (
        f"아래 문서 발췌에서 가장 중요한 전문용어/개념 {n}개를 뽑아줘.\n"
        '반드시 JSON으로만 출력해: {"cards": [{"term": "용어", "definition": "한두 문장 설명"}]}\n\n'
        f"[문서 발췌]\n{context}"
    )
    raw = llm.json(prompt)
    if isinstance(raw, dict):
        raw = raw.get("cards", [])
    cards = []
    for c in raw if isinstance(raw, list) else []:
        try:
            term, definition = str(c["term"]).strip(), str(c["definition"]).strip()
        except (KeyError, TypeError):
            continue
        if term and definition:
            cards.append({"term": term, "definition": definition})
    if not cards:
        raise LLMError("플래시카드를 만들지 못했어요. 다시 시도해 주세요.")
    return cards[:n]
