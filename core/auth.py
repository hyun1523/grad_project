"""회원가입 / 로그인.

비밀번호는 평문으로 저장하지 않고, 사용자별 무작위 salt + PBKDF2-HMAC-SHA256(20만 회)로 해시한다.
"""
import hashlib
import hmac
import re
import secrets
import sqlite3

from core import db

ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_가-힣]{3,20}$")


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS
    ).hex()


def register(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not USERNAME_RE.match(username):
        return False, "아이디는 3~20자의 한글, 영문, 숫자, _ 만 사용할 수 있어요."
    if len(password) < 6:
        return False, "비밀번호는 6자 이상이어야 해요."
    salt = secrets.token_hex(16)
    try:
        db.create_user(username, salt, _hash(password, salt))
    except sqlite3.IntegrityError:
        return False, "이미 사용 중인 아이디예요."
    return True, "회원가입이 완료됐어요. 로그인해 주세요."


def login(username: str, password: str):
    """성공하면 {'id', 'username'}, 실패하면 None."""
    user = db.get_user(username.strip())
    if user is None:
        # 존재하지 않는 아이디여도 같은 시간만큼 연산해 아이디 존재 여부 추측을 어렵게 한다.
        _hash(password, "00" * 16)
        return None
    if hmac.compare_digest(_hash(password, user["salt"]), user["pw_hash"]):
        return {"id": user["id"], "username": user["username"]}
    return None
