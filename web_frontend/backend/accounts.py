"""网页账号。每个账号有自己的对话库，密码只存哈希。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

WEB_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = WEB_ROOT / "data"
ACCOUNTS_DB = DATA_DIR / "accounts.sqlite3"
USERDB_ROOT = DATA_DIR / "userdbs"
LEGACY_DB = DATA_DIR / "sessions.sqlite3"
SECRET_PATH = Path.home() / ".config" / "moa" / "auth_secret"
NOTE_PATH = Path.home() / ".config" / "moa" / "basic_auth.txt"
COOKIE = "moa_user"
MAX_AGE = 14 * 24 * 3600
USERNAME_RE = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fff]{2,32}$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,64}$")

current_username: ContextVar[str | None] = ContextVar("moa_username", default=None)
router = APIRouter()
_HITS: dict[str, list[float]] = {}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


_DUMMY_HASH = hash_password("not-a-real-password")


def _restrict(path: Path, mode: int) -> None:
    if not path.exists():
        return
    os.chmod(path, mode)
    share = os.environ.get("MOA_SHARE_USER", "").strip()
    if not share:
        return
    subprocess.run(
        ["setfacl", "-m", f"u:{share}:rwX", os.fspath(path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _secret() -> bytes:
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_PATH.is_file():
        raw = SECRET_PATH.read_bytes().strip()
        if raw:
            return raw
    raw = secrets.token_hex(32).encode()
    SECRET_PATH.write_bytes(raw + b"\n")
    os.chmod(SECRET_PATH, 0o600)
    return raw


def _accounts() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ACCOUNTS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _db_file_for(username: str) -> Path:
    digest = hashlib.sha256(username.encode("utf-8")).hexdigest()[:20]
    return USERDB_ROOT / digest / "sessions.sqlite3"


def ensure_conversation_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _restrict(USERDB_ROOT, 0o700)
    _restrict(path.parent, 0o700)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              model TEXT,
              temperature REAL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              time TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        for statement in (
            "ALTER TABLE sessions ADD COLUMN is_shared INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE sessions ADD COLUMN storage_slug TEXT",
            "ALTER TABLE sessions ADD COLUMN workflow_status TEXT NOT NULL DEFAULT 'WAITING_INPUT'",
            "ALTER TABLE sessions ADD COLUMN plan_version INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE sessions ADD COLUMN plan_locked_at TEXT",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
    _restrict(path, 0o600)


def _table_exists(path: Path, table: str) -> bool:
    if not path.is_file():
        return False
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    return row is not None


def _count_rows(path: Path, table: str) -> int:
    if not _table_exists(path, table):
        return 0
    with sqlite3.connect(path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def init_accounts() -> None:
    with _accounts() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              username TEXT PRIMARY KEY,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              db_file TEXT NOT NULL DEFAULT ''
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "db_file" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN db_file TEXT NOT NULL DEFAULT ''")
    _import_legacy_users()
    if _user_count() == 0:
        _seed_from_note()
    _bind_conversation_files()
    _restrict(ACCOUNTS_DB, 0o600)


def _user_count() -> int:
    with _accounts() as conn:
        return int(conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])


def _import_legacy_users() -> None:
    if _user_count() or not _table_exists(LEGACY_DB, "users"):
        return
    with sqlite3.connect(LEGACY_DB) as source, _accounts() as dest:
        source.row_factory = sqlite3.Row
        rows = source.execute(
            "SELECT username, password_hash, created_at FROM users"
        ).fetchall()
        for row in rows:
            dest.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, created_at, db_file) VALUES (?, ?, ?, '')",
                (row["username"], row["password_hash"], row["created_at"]),
            )


def _seed_from_note() -> None:
    if not NOTE_PATH.is_file() or _user_count():
        return
    user = password = None
    for line in NOTE_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("user="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("password="):
            password = line.split("=", 1)[1]
    if user and password and USERNAME_RE.match(user):
        _insert_user(user, password)


def _insert_user(username: str, password: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _accounts() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at, db_file) VALUES (?, ?, ?, '')",
            (username, hash_password(password), now),
        )


def _bind_conversation_files() -> None:
    with _accounts() as conn:
        users = conn.execute(
            "SELECT username, created_at FROM users ORDER BY created_at ASC, username ASC"
        ).fetchall()
    if not users:
        return
    owner = users[0]["username"]
    legacy_sessions = _count_rows(LEGACY_DB, "sessions")
    if legacy_sessions > 0:
        dest = _db_file_for(owner)
        if not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LEGACY_DB, dest)
            if dest.stat().st_size != LEGACY_DB.stat().st_size:
                dest.unlink(missing_ok=True)
                raise RuntimeError("复制对话库失败")
            _restrict(dest, 0o600)
            _restrict(dest.parent, 0o700)
        migrated = DATA_DIR / "sessions.sqlite3.migrated"
        if not migrated.exists():
            LEGACY_DB.rename(migrated)
        _restrict(migrated, 0o600)
    for row in users:
        path = _db_file_for(row["username"])
        ensure_conversation_schema(path)
        with _accounts() as conn:
            conn.execute(
                "UPDATE users SET db_file=? WHERE username=?",
                (str(path), row["username"]),
            )


def create_user(username: str, password: str) -> None:
    _insert_user(username, password)
    path = _db_file_for(username)
    ensure_conversation_schema(path)
    with _accounts() as conn:
        conn.execute(
            "UPDATE users SET db_file=? WHERE username=?",
            (str(path), username),
        )


def db_path_for(username: str) -> Path:
    with _accounts() as conn:
        row = conn.execute(
            "SELECT db_file FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if row is None or not row["db_file"]:
        raise LookupError(username)
    return Path(row["db_file"])


def open_conversation_db() -> Path:
    username = current_username.get()
    if not username:
        raise LookupError("no account")
    path = db_path_for(username)
    ensure_conversation_schema(path)
    return path


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(rounds)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def authenticate(username: str, password: str) -> bool:
    with _accounts() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username=?",
            (username,),
        ).fetchone()
    stored = row["password_hash"] if row else _DUMMY_HASH
    ok = verify_password(password, stored)
    return bool(row) and ok


def user_exists(username: str) -> bool:
    with _accounts() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE username=?",
            (username,),
        ).fetchone()
    return row is not None


def issue_token(username: str) -> str:
    exp = int(time.time()) + MAX_AGE
    payload = f"{username}|{exp}".encode()
    sig = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
    blob = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{blob}.{sig}"


def read_token(token: str) -> str | None:
    try:
        blob, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4))
        expected = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        username, exp = payload.decode().rsplit("|", 1)
        if int(exp) < int(time.time()):
            return None
        if not user_exists(username):
            return None
        return username
    except (ValueError, TypeError):
        return None


def _cookie_user(headers) -> str | None:
    raw = ""
    for key, value in headers:
        if key == b"cookie":
            raw = value.decode("latin1")
            break
    for part in raw.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE and value:
            return read_token(value)
    return None


def _set_cookie(response, username: str) -> None:
    response.set_cookie(
        COOKIE,
        issue_token(username),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-real-ip") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _limited(key: str, limit: int, window: int) -> bool:
    now = time.time()
    hits = [item for item in _HITS.get(key, []) if now - item < window]
    if len(hits) >= limit:
        _HITS[key] = hits
        return True
    hits.append(now)
    _HITS[key] = hits
    return False


def _check_new_account(username: str, password: str) -> str | None:
    if not USERNAME_RE.match(username or ""):
        return "用户名需要 2–32 位，可使用字母、数字、下划线或中文"
    if not isinstance(password, str) or not PASSWORD_RE.match(password):
        return "密码需要 8–64 位，并且同时包含字母和数字"
    if password.lower() == username.lower():
        return "密码不能和用户名相同"
    if user_exists(username):
        return "该用户名已被注册"
    return None


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        public = (
            path in {"/login", "/register", "/favicon.ico"}
            or path.startswith("/static/")
            or path.startswith("/api/auth/")
        )
        user = _cookie_user(scope.get("headers") or [])
        if public:
            await self.app(scope, receive, send)
            return
        if user:
            token = current_username.set(user)
            scope.setdefault("state", {})["user"] = user
            try:
                await self.app(scope, receive, send)
            finally:
                current_username.reset(token)
            return
        if path.startswith("/api/"):
            body = '{"detail":"未登录"}'.encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"application/json; charset=utf-8"],
                        [b"content-length", str(len(body)).encode()],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await send(
            {
                "type": "http.response.start",
                "status": 303,
                "headers": [[b"location", b"/login"]],
            }
        )
        await send({"type": "http.response.body", "body": b""})


def install(app) -> None:
    init_accounts()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)


def _request_user(request: Request) -> str | None:
    return read_token(request.cookies.get(COOKIE, ""))


@router.api_route("/login", methods=["GET", "HEAD"])
@router.api_route("/register", methods=["GET", "HEAD"])
def auth_page(request: Request):
    if _request_user(request):
        return RedirectResponse("/", status_code=303)
    return FileResponse(
        str(WEB_ROOT / "auth.html"),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/api/auth/me")
def auth_me(request: Request):
    user = _request_user(request)
    if not user:
        return JSONResponse({"detail": "未登录"}, status_code=401)
    return {"username": user}


@router.post("/api/auth/register")
async def auth_register(request: Request):
    if _limited(f"reg:{_client_key(request)}", 8, 3600):
        return JSONResponse({"detail": "注册过于频繁，请稍后再试"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "请求格式不正确"}, status_code=400)
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    error = _check_new_account(username, password)
    if error:
        status = 409 if error == "该用户名已被注册" else 400
        return JSONResponse({"detail": error}, status_code=status)
    create_user(username, password)
    response = JSONResponse({"username": username})
    _set_cookie(response, username)
    return response


@router.post("/api/auth/login")
async def auth_login(request: Request):
    key = f"login:{_client_key(request)}"
    if _limited(key, 10, 600):
        return JSONResponse({"detail": "尝试次数过多，请稍后再试"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "请求格式不正确"}, status_code=400)
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not authenticate(username, password):
        return JSONResponse({"detail": "账号或密码不正确"}, status_code=401)
    _HITS.pop(key, None)
    response = JSONResponse({"username": username})
    _set_cookie(response, username)
    return response


@router.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE, path="/")
    return response
