"""문서 분할과 검색(RAG의 Retrieval 부분).

외부 임베딩 API 없이 동작하도록 BM25를 직접 구현했다.
한국어는 조사/어미 때문에 공백 기준 토큰화가 잘 맞지 않아서,
한글 구간은 글자 2-gram, 영어/숫자는 단어 단위로 토큰을 만든다.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9]+|[가-힣ㄱ-ㅎㅏ-ㅣ一-龥ぁ-ゟ゠-ヿ]+")
_CJK_RE = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ一-龥ぁ-ゟ゠-ヿ]+")


@dataclass
class Chunk:
    page: int
    text: str


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in _WORD_RE.findall(text.lower()):
        if _CJK_RE.fullmatch(word):
            if len(word) == 1:
                tokens.append(word)
            else:
                tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
        else:
            tokens.append(word)
    return tokens


def chunk_pages(pages: list[str], max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    """페이지별로 나누되, 긴 페이지는 겹치게 잘라서 문맥이 끊기지 않게 한다. 출처 표시를 위해 페이지 번호를 유지한다."""
    chunks: list[Chunk] = []
    step = max(1, max_chars - overlap)
    for page_no, text in enumerate(pages, start=1):
        text = text.strip()
        if not text:
            continue
        if len(text) <= max_chars:
            chunks.append(Chunk(page_no, text))
            continue
        for start in range(0, len(text), step):
            piece = text[start : start + max_chars].strip()
            if piece:
                chunks.append(Chunk(page_no, piece))
            if start + max_chars >= len(text):
                break
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.doc_tokens = [Counter(tokenize(c.text)) for c in chunks]
        self.doc_len = [sum(c.values()) for c in self.doc_tokens]
        self.avg_len = (sum(self.doc_len) / len(chunks)) if chunks else 0.0
        df: Counter = Counter()
        for counter in self.doc_tokens:
            df.update(counter.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, top_k: int = 5) -> list[Chunk]:
        q_tokens = set(tokenize(query))
        if not q_tokens or not self.chunks:
            return []
        scored: list[tuple[float, int]] = []
        for i, counter in enumerate(self.doc_tokens):
            score = 0.0
            for t in q_tokens:
                tf = counter.get(t, 0)
                if tf == 0:
                    continue
                norm = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / (self.avg_len or 1))
                score += self.idf[t] * tf * (self.k1 + 1) / norm
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: -x[0])
        return [self.chunks[i] for _, i in scored[:top_k]]


def group_for_summary(pages: list[str], max_chars: int = 9000) -> list[tuple[int, int, str]]:
    """요약용으로 페이지를 순서대로 묶는다. (시작 페이지, 끝 페이지, 텍스트) 리스트를 반환."""
    groups: list[tuple[int, int, str]] = []
    buf: list[str] = []
    start = None
    size = 0
    for page_no, text in enumerate(pages, start=1):
        if not text.strip():
            continue
        if start is None:
            start = page_no
        if buf and size + len(text) > max_chars:
            groups.append((start, page_no - 1, "\n".join(buf)))
            buf, start, size = [], page_no, 0
        buf.append(f"[p.{page_no}]\n{text}")
        size += len(text)
    if buf and start is not None:
        last = max(i for i, t in enumerate(pages, start=1) if t.strip())
        groups.append((start, last, "\n".join(buf)))
    return groups


def sample_evenly(chunks: list[Chunk], n: int) -> list[Chunk]:
    """문서 전체에서 골고루 n개의 조각을 뽑는다(앞부분만 쏠리지 않게)."""
    if len(chunks) <= n:
        return list(chunks)
    step = len(chunks) / n
    return [chunks[int(i * step)] for i in range(n)]
