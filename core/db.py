"""SQLite 데이터베이스 계층.

사용자, 문서(페이지별 텍스트), 요약, 대화, 퀴즈 문제, 풀이 기록, 플래시카드를 저장한다.
모든 함수는 호출 시마다 짧게 연결을 열고 닫아 Streamlit의 재실행 모델과 충돌하지 않게 한다.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "study_partner.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL,
    pw_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    total_pages INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS pages (
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (doc_id, page_no)
);
CREATE TABLE IF NOT EXISTS summaries (
    doc_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    answer_idx INTEGER NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    page INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    selected_idx INTEGER NOT NULL,
    is_correct INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS flashcards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    definition TEXT NOT NULL
);
"""


def get_db_path() -> str:
    return os.environ.get("STUDY_DB_PATH", str(DEFAULT_DB_PATH))


@contextmanager
def connect():
    path = get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# ---------- 사용자 ----------
def create_user(username: str, salt: str, pw_hash: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, salt, pw_hash) VALUES (?, ?, ?)",
            (username, salt, pw_hash),
        )
        return cur.lastrowid


def get_user(username: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


# ---------- 문서 ----------
def add_document(user_id: int, name: str, pages: list[str]) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO documents (user_id, name, total_pages) VALUES (?, ?, ?)",
            (user_id, name, len(pages)),
        )
        doc_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO pages (doc_id, page_no, text) VALUES (?, ?, ?)",
            [(doc_id, i + 1, t) for i, t in enumerate(pages)],
        )
        return doc_id


def list_documents(user_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM documents WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()


def get_document(doc_id: int, user_id: int):
    """다른 사용자의 문서에 접근하지 못하도록 user_id까지 함께 검사한다."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)
        ).fetchone()


def get_pages(doc_id: int) -> list[tuple[int, str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT page_no, text FROM pages WHERE doc_id = ? ORDER BY page_no", (doc_id,)
        ).fetchall()
        return [(r["page_no"], r["text"]) for r in rows]


def delete_document(doc_id: int, user_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))


# ---------- 요약 ----------
def save_summary(doc_id: int, content: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO summaries (doc_id, content) VALUES (?, ?) "
            "ON CONFLICT(doc_id) DO UPDATE SET content = excluded.content, "
            "created_at = datetime('now', 'localtime')",
            (doc_id, content),
        )


def get_summary(doc_id: int):
    with connect() as conn:
        row = conn.execute("SELECT content FROM summaries WHERE doc_id = ?", (doc_id,)).fetchone()
        return row["content"] if row else None


# ---------- 대화 ----------
def add_chat(doc_id: int, role: str, content: str, sources: list[int] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO chats (doc_id, role, content, sources) VALUES (?, ?, ?, ?)",
            (doc_id, role, content, json.dumps(sources or [])),
        )


def get_chats(doc_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, sources FROM chats WHERE doc_id = ? ORDER BY id", (doc_id,)
        ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "sources": json.loads(r["sources"])}
            for r in rows
        ]


def clear_chats(doc_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM chats WHERE doc_id = ?", (doc_id,))


# ---------- 퀴즈 ----------
def add_questions(doc_id: int, questions: list[dict]) -> list[int]:
    ids = []
    with connect() as conn:
        for q in questions:
            cur = conn.execute(
                "INSERT INTO questions (doc_id, question, options, answer_idx, explanation, topic, page) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_id,
                    q["question"],
                    json.dumps(q["options"], ensure_ascii=False),
                    q["answer_idx"],
                    q.get("explanation", ""),
                    q.get("topic", ""),
                    q.get("page"),
                ),
            )
            ids.append(cur.lastrowid)
    return ids


def _row_to_question(r) -> dict:
    return {
        "id": r["id"],
        "doc_id": r["doc_id"],
        "question": r["question"],
        "options": json.loads(r["options"]),
        "answer_idx": r["answer_idx"],
        "explanation": r["explanation"],
        "topic": r["topic"],
        "page": r["page"],
    }


def get_questions(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM questions WHERE id IN ({marks})", ids).fetchall()
    by_id = {r["id"]: _row_to_question(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def get_recent_question_texts(doc_id: int, limit: int = 15) -> list[str]:
    """새 퀴즈를 낼 때 겹치지 않도록 최근에 낸 문제 문장을 돌려준다."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT question FROM questions WHERE doc_id = ? ORDER BY id DESC LIMIT ?",
            (doc_id, limit),
        ).fetchall()
    return [r["question"] for r in rows]


def record_attempt(user_id: int, question_id: int, selected_idx: int, is_correct: bool) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO attempts (user_id, question_id, selected_idx, is_correct) VALUES (?, ?, ?, ?)",
            (user_id, question_id, selected_idx, 1 if is_correct else 0),
        )


def get_wrong_questions(user_id: int, doc_id: int | None = None) -> list[dict]:
    """가장 최근 풀이가 오답인 문제 목록(다시 맞히면 오답 노트에서 빠진다)."""
    sql = (
        "SELECT q.*, a.selected_idx AS last_selected, "
        "(SELECT COUNT(*) FROM attempts x WHERE x.user_id = ? AND x.question_id = q.id AND x.is_correct = 0) AS wrong_count "
        "FROM questions q JOIN attempts a ON a.question_id = q.id AND a.user_id = ? "
        "WHERE a.id = (SELECT MAX(id) FROM attempts WHERE user_id = ? AND question_id = q.id) "
        "AND a.is_correct = 0"
    )
    params: list = [user_id, user_id, user_id]
    if doc_id is not None:
        sql += " AND q.doc_id = ?"
        params.append(doc_id)
    sql += " ORDER BY a.id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = _row_to_question(r)
        d["last_selected"] = r["last_selected"]
        d["wrong_count"] = r["wrong_count"]
        out.append(d)
    return out


# ---------- 통계 ----------
def get_stats(user_id: int) -> dict:
    with connect() as conn:
        total, correct = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(is_correct), 0) FROM attempts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        daily = conn.execute(
            "SELECT date(created_at) AS day, COUNT(*) AS solved, SUM(is_correct) AS correct "
            "FROM attempts WHERE user_id = ? GROUP BY date(created_at) ORDER BY day",
            (user_id,),
        ).fetchall()
        topics = conn.execute(
            "SELECT q.topic AS topic, COUNT(*) AS solved, SUM(a.is_correct) AS correct "
            "FROM attempts a JOIN questions q ON q.id = a.question_id "
            "WHERE a.user_id = ? AND q.topic != '' GROUP BY q.topic ORDER BY solved DESC",
            (user_id,),
        ).fetchall()
        docs = conn.execute(
            "SELECT d.name AS name, COUNT(a.id) AS solved, COALESCE(SUM(a.is_correct), 0) AS correct "
            "FROM documents d LEFT JOIN questions q ON q.doc_id = d.id "
            "LEFT JOIN attempts a ON a.question_id = q.id AND a.user_id = ? "
            "WHERE d.user_id = ? GROUP BY d.id ORDER BY d.id DESC",
            (user_id, user_id),
        ).fetchall()
        doc_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    return {
        "total": total,
        "correct": correct,
        "doc_count": doc_count,
        "daily": [dict(r) for r in daily],
        "topics": [dict(r) for r in topics],
        "docs": [dict(r) for r in docs],
    }


# ---------- 플래시카드 ----------
def save_flashcards(doc_id: int, cards: list[dict]) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM flashcards WHERE doc_id = ?", (doc_id,))
        conn.executemany(
            "INSERT INTO flashcards (doc_id, term, definition) VALUES (?, ?, ?)",
            [(doc_id, c["term"], c["definition"]) for c in cards],
        )


def get_flashcards(doc_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT term, definition FROM flashcards WHERE doc_id = ? ORDER BY id", (doc_id,)
        ).fetchall()
        return [dict(r) for r in rows]
