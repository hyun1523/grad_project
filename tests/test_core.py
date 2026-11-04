"""핵심 로직 테스트. 실제 Gemini API 없이 가짜 LLM으로 검증한다.  실행: python -m pytest -q"""
import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import auth, db, rag, study  # noqa: E402
from core.llm import GeminiLLM, LLMError, parse_json  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDY_DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


class FakeLLM:
    def __init__(self, json_reply=None):
        self.json_reply = json_reply
        self.prompts = []

    def text(self, prompt):
        self.prompts.append(prompt)
        return "요약 결과"

    def json(self, prompt):
        self.prompts.append(prompt)
        return self.json_reply


PAGES = [
    "운영체제는 하드웨어 자원을 관리하는 소프트웨어이다. 프로세스는 실행 중인 프로그램을 말한다.",
    "스케줄링은 CPU를 어떤 프로세스에 줄지 정하는 방법이다. 라운드 로빈은 시간 할당량을 돌려가며 쓴다.",
    "",
    "가상 메모리는 물리 메모리보다 큰 주소 공간을 제공한다. 페이지 교체 알고리즘에는 LRU가 있다.",
]


# ---------- auth ----------
def test_register_and_login():
    assert auth.register("byeonghyun", "secret1")[0]
    assert auth.login("byeonghyun", "secret1")["username"] == "byeonghyun"
    assert auth.login("byeonghyun", "wrong") is None
    assert auth.login("nobody", "secret1") is None


def test_register_rejects_bad_input_and_duplicates():
    assert not auth.register("ab", "secret1")[0]
    assert not auth.register("validname", "123")[0]
    assert auth.register("validname", "secret1")[0]
    ok, msg = auth.register("validname", "another1")
    assert not ok and "이미" in msg


def test_password_is_not_stored_plain():
    auth.register("tester", "mypassword")
    user = db.get_user("tester")
    assert "mypassword" not in user["pw_hash"] and len(user["pw_hash"]) == 64


# ---------- documents / isolation ----------
def test_documents_are_isolated_per_user():
    auth.register("userone", "secret1")
    auth.register("usertwo", "secret1")
    u1, u2 = auth.login("userone", "secret1"), auth.login("usertwo", "secret1")
    doc_id = db.add_document(u1["id"], "os.pdf", PAGES)
    assert db.get_document(doc_id, u1["id"]) is not None
    assert db.get_document(doc_id, u2["id"]) is None  # 다른 사용자는 접근 불가
    db.delete_document(doc_id, u2["id"])  # 남의 문서 삭제 시도는 무시
    assert db.get_document(doc_id, u1["id"]) is not None
    assert db.get_pages(doc_id)[3][0] == 4


# ---------- rag ----------
def test_chunking_keeps_page_numbers_and_skips_empty():
    chunks = rag.chunk_pages(PAGES)
    assert [c.page for c in chunks] == [1, 2, 4]
    long = rag.chunk_pages(["가" * 3000], max_chars=1000, overlap=100)
    assert len(long) >= 3 and all(c.page == 1 for c in long)
    assert all(len(c.text) <= 1000 for c in long)


def test_korean_search_finds_right_page():
    index = rag.BM25Index(rag.chunk_pages(PAGES))
    assert index.search("가상 메모리가 뭐야?", top_k=1)[0].page == 4
    assert index.search("라운드 로빈 스케줄링", top_k=1)[0].page == 2
    assert index.search("전혀관계없는질문xyz") == []


def test_group_for_summary_covers_all_pages():
    pages = ["가" * 400] * 10
    groups = rag.group_for_summary(pages, max_chars=1000)
    assert groups[0][0] == 1 and groups[-1][1] == 10
    assert len(groups) > 1


def test_long_document_summary_uses_all_pages_not_just_first_chars():
    pages = [f"{i}쪽 내용 " + "내용" * 500 for i in range(1, 41)]
    llm = FakeLLM()
    study.summarize_document(llm, pages)
    joined = "\n".join(llm.prompts)
    assert "40쪽 내용" in joined  # 예전 코드는 앞 1만 자만 보냈다
    assert len(llm.prompts) <= study.MAX_SUMMARY_GROUPS + 1


# ---------- quiz ----------
GOOD_Q = {
    "question": "LRU는 무엇의 예인가?",
    "options": ["페이지 교체", "스케줄링", "파일 시스템", "네트워크"],
    "answer_idx": 0,
    "explanation": "LRU는 페이지 교체 알고리즘이다.",
    "topic": "가상 메모리",
    "page": 4,
}


def test_validate_questions_filters_and_remaps_answer():
    bad = [
        {"question": "보기 부족", "options": ["a", "b"], "answer_idx": 0},
        {"question": "정답 범위 밖", "options": ["a", "b", "c", "d"], "answer_idx": 7},
        {"question": "보기 중복", "options": ["a", "a", "c", "d"], "answer_idx": 0},
        {"no_question": True},
    ]
    for seed in range(20):
        out = study.validate_questions({"questions": bad + [GOOD_Q]}, random.Random(seed))
        assert len(out) == 1
        q = out[0]
        assert q["options"][q["answer_idx"]] == "페이지 교체"  # 섞어도 정답이 유지돼야 한다
        assert sorted(q["options"]) == sorted(GOOD_Q["options"])


def test_generate_quiz_and_weak_topic_mode():
    index = rag.BM25Index(rag.chunk_pages(PAGES))
    llm = FakeLLM({"questions": [GOOD_Q]})
    qs = study.generate_quiz(llm, index, n=3, rng=random.Random(1))
    assert len(qs) == 1
    qs = study.generate_quiz(llm, index, n=3, topics=["가상 메모리"], avoid=["이전 문제"])
    assert "가상 메모리" in llm.prompts[-1] and "이전 문제" in llm.prompts[-1]
    assert "[p.4]" in llm.prompts[-1]


def test_generate_quiz_raises_when_ai_returns_garbage():
    index = rag.BM25Index(rag.chunk_pages(PAGES))
    with pytest.raises(LLMError):
        study.generate_quiz(FakeLLM({"questions": [{"x": 1}]}), index)


def test_answer_question_returns_source_pages():
    index = rag.BM25Index(rag.chunk_pages(PAGES))
    llm = FakeLLM()
    answer, pages = study.answer_question(llm, index, [], "가상 메모리란?")
    assert 4 in pages and "[p.4]" in llm.prompts[-1]
    answer, pages = study.answer_question(llm, index, [], "zzzz qqqq")
    assert pages == [] and "찾지 못" in answer


# ---------- DB: attempts / wrong notes / stats ----------
def test_wrong_note_and_stats():
    auth.register("student", "secret1")
    uid = auth.login("student", "secret1")["id"]
    doc_id = db.add_document(uid, "os.pdf", PAGES)
    q1, q2 = db.add_questions(
        doc_id, [GOOD_Q, {**GOOD_Q, "question": "두번째 문제", "topic": "스케줄링"}]
    )
    db.record_attempt(uid, q1, 1, False)
    db.record_attempt(uid, q2, 0, True)
    wrong = db.get_wrong_questions(uid)
    assert [w["id"] for w in wrong] == [q1] and wrong[0]["wrong_count"] == 1
    db.record_attempt(uid, q1, 0, True)  # 다시 맞히면 오답 노트에서 빠진다
    assert db.get_wrong_questions(uid) == []
    s = db.get_stats(uid)
    assert s["total"] == 3 and s["correct"] == 2 and s["doc_count"] == 1
    assert {t["topic"] for t in s["topics"]} == {"가상 메모리", "스케줄링"}


def test_chat_persistence_and_summary_upsert_and_flashcards():
    auth.register("student", "secret1")
    uid = auth.login("student", "secret1")["id"]
    doc_id = db.add_document(uid, "a.pdf", PAGES)
    db.add_chat(doc_id, "user", "질문")
    db.add_chat(doc_id, "assistant", "답", [4])
    assert db.get_chats(doc_id)[1]["sources"] == [4]
    db.save_summary(doc_id, "v1")
    db.save_summary(doc_id, "v2")
    assert db.get_summary(doc_id) == "v2"
    db.save_flashcards(doc_id, [{"term": "LRU", "definition": "가장 오래 안 쓴 페이지 교체"}])
    assert db.get_flashcards(doc_id)[0]["term"] == "LRU"
    db.delete_document(doc_id, uid)  # 연관 데이터까지 함께 삭제(CASCADE)
    assert db.get_chats(doc_id) == [] and db.get_summary(doc_id) is None


# ---------- llm wrapper ----------
def test_parse_json_variants():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n[1, 2]\n```') == [1, 2]
    assert parse_json('설명입니다 {"a": [1]} 끝') == {"a": [1]}
    with pytest.raises(ValueError):
        parse_json("그냥 문장")


class _Resp:
    def __init__(self, text):
        self.text = text


class _FlakyModels:
    def __init__(self, fail_times, error="503 UNAVAILABLE"):
        self.calls, self.fail_times, self.error = 0, fail_times, error

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(self.error)
        return _Resp("ok")


class _Client:
    def __init__(self, models):
        self.models = models


def test_llm_retries_then_succeeds():
    models = _FlakyModels(2)
    llm = GeminiLLM("k", client=_Client(models), sleep=lambda s: None)
    assert llm.text("hi") == "ok" and models.calls == 3


def test_llm_gives_friendly_error_on_quota():
    llm = GeminiLLM("k", client=_Client(_FlakyModels(99, "429 RESOURCE_EXHAUSTED")), sleep=lambda s: None)
    with pytest.raises(LLMError, match="한도"):
        llm.text("hi")


def test_llm_json_mode_retries_on_bad_format():
    class Models:
        calls = 0

        def generate_content(self, **kwargs):
            Models.calls += 1
            return _Resp("not json" if Models.calls == 1 else json.dumps({"ok": True}))

    # json 모드는 google.genai.types가 필요해서, 설치된 환경에서만 이 경로를 검증한다
    pytest.importorskip("google.genai")
    llm = GeminiLLM("k", client=_Client(Models()), sleep=lambda s: None)
    assert llm.json("x") == {"ok": True}
