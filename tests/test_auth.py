"""認證功能測試。

【新手導讀】測試的目的是「自動化地驗證你的程式是否正確」。
每個測試函式（test_ 開頭）代表一個測試案例：
- 模擬使用者的操作（送出表單、訪問頁面等）
- 檢查結果是否符合預期（狀態碼、頁面內容等）

TestClient 是 FastAPI 提供的「模擬瀏覽器」，
讓你在不啟動伺服器的情況下測試 API。

執行測試的指令：uv run pytest tests/test_auth.py -v
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_db():
    """每個測試前重置資料庫（確保測試之間互不影響）。"""
    import asyncio
    from app.database import engine, Base

    async def _reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_reset())


@pytest.fixture
def client():
    """建立 TestClient 並初始化資料庫。"""
    from app.main import app

    with TestClient(app) as c:
        yield c


def _register_user(client: TestClient, username: str = "testuser", password: str = "testpass123"):
    """輔助函式：註冊一個使用者。"""
    return client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def _login_user(client: TestClient, username: str = "testuser", password: str = "testpass123"):
    """輔助函式：登入。"""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


# === 註冊測試 ===


class TestRegister:
    """使用者註冊相關測試。"""

    def test_register_page_loads(self, client):
        """GET /register 應顯示註冊頁面。"""
        resp = client.get("/register")
        assert resp.status_code == 200
        assert "建立帳號" in resp.text

    def test_register_success(self, client):
        """成功註冊後應 302 導向首頁。"""
        resp = _register_user(client)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"

    def test_register_duplicate_username(self, client):
        """註冊重複帳號應顯示錯誤。"""
        _register_user(client)
        resp = _register_user(client)
        assert resp.status_code == 200
        assert "此帳號已被使用" in resp.text

    def test_register_short_username(self, client):
        """帳號太短應顯示錯誤。"""
        resp = _register_user(client, username="ab")
        assert resp.status_code == 200
        assert "3~30" in resp.text

    def test_register_invalid_username(self, client):
        """帳號含特殊字元應顯示錯誤。"""
        resp = _register_user(client, username="test user!")
        assert resp.status_code == 200
        assert "英文字母" in resp.text

    def test_register_short_password(self, client):
        """密碼太短應顯示錯誤。"""
        resp = _register_user(client, password="short")
        assert resp.status_code == 200
        assert "8" in resp.text


# === 登入測試 ===


class TestLogin:
    """使用者登入相關測試。"""

    def test_login_page_loads(self, client):
        """GET /login 應顯示登入頁面。"""
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "登入" in resp.text

    def test_login_success(self, client):
        """正確帳密應登入成功並 302 導向首頁。"""
        _register_user(client)
        resp = _login_user(client)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"

    def test_login_wrong_password(self, client):
        """錯誤密碼應顯示統一錯誤訊息。"""
        _register_user(client)
        resp = _login_user(client, password="wrongpassword")
        assert resp.status_code == 200
        assert "帳號或密碼錯誤" in resp.text

    def test_login_nonexistent_user(self, client):
        """不存在的帳號應顯示統一錯誤訊息（不洩漏帳號是否存在）。"""
        resp = _login_user(client, username="nouser", password="somepass123")
        assert resp.status_code == 200
        assert "帳號或密碼錯誤" in resp.text

    def test_login_expired_shows_message(self, client):
        """expired=1 參數應顯示過期提示。"""
        resp = client.get("/login?expired=1")
        assert resp.status_code == 200
        assert "登入已過期" in resp.text

    def test_login_with_next_redirect(self, client):
        """登入成功後應導向 next 參數指定的頁面。"""
        _register_user(client)
        resp = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass123", "next": "/meetings"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == "/meetings"


# === 登出測試 ===


class TestLogout:
    """使用者登出相關測試。"""

    def test_logout_success(self, client):
        """登出後應 302 導向登入頁。"""
        _register_user(client)
        resp = client.post("/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]


# === 路由保護測試 ===


class TestProtectedRoutes:
    """受保護路由的認證檢查測試。"""

    def test_homepage_requires_login(self, client):
        """未登入訪問首頁應被導向登入頁。"""
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 307
        assert "/login" in resp.headers["location"]

    def test_api_requires_login(self, client):
        """未登入呼叫 API 應收到 401。"""
        resp = client.get("/api/meetings")
        assert resp.status_code == 401

    def test_authenticated_access(self, client):
        """登入後應能正常訪問受保護頁面。"""
        _register_user(client)
        resp = client.get("/", follow_redirects=True)
        assert resp.status_code == 200
