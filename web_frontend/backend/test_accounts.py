"""账号哈希、密码规则，以及每人独立的对话库。不碰正在使用的库。"""
import sqlite3
import tempfile
from pathlib import Path

from web_frontend.backend import accounts


def test_register_rules_and_separate_databases():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        accounts.ACCOUNTS_DB = root / "accounts.sqlite3"
        accounts.USERDB_ROOT = root / "userdbs"
        accounts.LEGACY_DB = root / "missing.sqlite3"
        accounts.DATA_DIR = root
        accounts.SECRET_PATH = root / "auth_secret"
        accounts.NOTE_PATH = root / "missing.txt"
        accounts._HITS.clear()
        accounts.init_accounts()

        assert accounts._check_new_account("ab", "abcdefgh")
        assert accounts._check_new_account("chen", "chenchen")
        assert accounts._check_new_account("chen", "chenpass1") is None

        accounts.create_user("chen", "chenpass1")
        accounts.create_user("li", "lipass123")
        assert accounts._check_new_account("chen", "chenpass1") == "该用户名已被注册"
        assert accounts.authenticate("chen", "chenpass1")
        assert not accounts.authenticate("chen", "wrongpass1")

        token = accounts.current_username.set("chen")
        chen_db = accounts.open_conversation_db()
        with sqlite3.connect(chen_db) as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES ('s1', '仅陈', 't', 't')"
            )
        assert accounts._count_rows(chen_db, "sessions") == 1

        accounts.current_username.set("li")
        li_db = accounts.open_conversation_db()
        assert li_db != chen_db
        assert accounts._count_rows(li_db, "sessions") == 0
        accounts.current_username.reset(token)

        issued = accounts.issue_token("chen")
        assert accounts.read_token(issued) == "chen"
        assert accounts.read_token(issued + "x") is None


if __name__ == "__main__":
    test_register_rules_and_separate_databases()
    print("ok")
