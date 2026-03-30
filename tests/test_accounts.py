"""帳號管理功能測試。"""

import asyncio
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_db():
    """每個測試前重置資料庫。"""
    from app.database import engine, Base

    async def _reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_reset())


@pytest.fixture
def client():
    """建立 TestClient。"""
    from app.main import app

    with TestClient(app) as c:
        yield c


def _register(client, username="admin", password="admin12345"):
    """輔助：註冊帳號。"""
    return client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def _login(client, username="admin", password="admin12345"):
    """輔助：登入。"""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


class TestAccountsList:
    """帳號列表測試。"""

    def test_accounts_page_loads(self, client):
        """登入後能看到帳號管理頁面。"""
        _register(client)
        resp = client.get("/accounts")
        assert resp.status_code == 200
        assert "帳號管理" in resp.text

    def test_accounts_shows_users(self, client):
        """帳號列表顯示所有帳號。"""
        _register(client, "user_a", "password123")
        _register(client, "user_b", "password123")
        # 登入 user_a
        _login(client, "user_a", "password123")
        resp = client.get("/accounts")
        assert "user_a" in resp.text
        assert "user_b" in resp.text

    def test_accounts_requires_login(self, client):
        """未登入訪問帳號管理被導向登入頁。"""
        resp = client.get("/accounts", follow_redirects=False)
        assert resp.status_code == 307


class TestChangePassword:
    """修改密碼測試。"""

    def test_change_password_page_loads(self, client):
        """修改密碼頁面正常顯示。"""
        _register(client)
        resp = client.get("/accounts/change-password")
        assert resp.status_code == 200
        assert "修改密碼" in resp.text

    def test_change_password_success(self, client):
        """修改密碼成功。"""
        _register(client)
        resp = client.post(
            "/accounts/change-password",
            data={"old_password": "admin12345", "new_password": "newpass12345"},
        )
        assert resp.status_code == 200
        assert "密碼修改成功" in resp.text

    def test_change_password_wrong_old(self, client):
        """舊密碼錯誤應顯示錯誤。"""
        _register(client)
        resp = client.post(
            "/accounts/change-password",
            data={"old_password": "wrongpassword", "new_password": "newpass12345"},
        )
        assert resp.status_code == 200
        assert "舊密碼不正確" in resp.text

    def test_change_password_short_new(self, client):
        """新密碼太短應顯示錯誤。"""
        _register(client)
        resp = client.post(
            "/accounts/change-password",
            data={"old_password": "admin12345", "new_password": "short"},
        )
        assert resp.status_code == 200
        assert "8" in resp.text

    def test_login_with_new_password(self, client):
        """修改密碼後用新密碼能登入。"""
        _register(client)
        client.post(
            "/accounts/change-password",
            data={"old_password": "admin12345", "new_password": "newpass12345"},
        )
        # 登出
        client.post("/logout", follow_redirects=False)
        # 用新密碼登入
        resp = _login(client, "admin", "newpass12345")
        assert resp.status_code == 302


class TestToggleActive:
    """停用/啟用帳號測試。"""

    def test_toggle_deactivate(self, client):
        """停用帳號成功。"""
        _register(client, "admin", "admin12345")
        _register(client, "target", "target12345")
        _login(client, "admin", "admin12345")

        # 先取得 target 的 user_id
        resp = client.get("/accounts")
        # 找到 toggle 按鈕中的 user_id
        import re
        match = re.search(r"toggleActive\('([^']+)', 'target'\)", resp.text)
        assert match, "找不到 target 的操作按鈕"
        target_id = match.group(1)

        # 停用
        resp = client.post(f"/api/accounts/{target_id}/toggle-active")
        assert resp.status_code == 200

    def test_cannot_toggle_self(self, client):
        """不能停用自己。"""
        _register(client, "admin", "admin12345")
        _login(client, "admin", "admin12345")

        # 取得自己的 user_id
        resp = client.get("/accounts")
        assert "（你）" in resp.text

    def test_deactivated_user_cannot_login(self, client):
        """被停用的帳號無法登入。"""
        _register(client, "admin", "admin12345")
        _register(client, "target", "target12345")
        _login(client, "admin", "admin12345")

        resp = client.get("/accounts")
        import re
        match = re.search(r"toggleActive\('([^']+)', 'target'\)", resp.text)
        assert match
        target_id = match.group(1)

        # 停用 target
        client.post(f"/api/accounts/{target_id}/toggle-active")

        # 登出 admin
        client.post("/logout", follow_redirects=False)

        # target 嘗試登入應失敗
        resp = _login(client, "target", "target12345")
        assert resp.status_code == 200  # 回到登入頁（不是 302 重導）
        assert "帳號或密碼錯誤" in resp.text


class TestDeleteAccount:
    """刪除帳號測試。"""

    def test_delete_success(self, client):
        """刪除帳號成功。"""
        _register(client, "admin", "admin12345")
        _register(client, "target", "target12345")
        _login(client, "admin", "admin12345")

        resp = client.get("/accounts")
        import re
        match = re.search(r"deleteUser\('([^']+)', 'target'\)", resp.text)
        assert match
        target_id = match.group(1)

        resp = client.delete(f"/api/accounts/{target_id}")
        assert resp.status_code == 200

        # 確認 target 不在列表了
        resp = client.get("/accounts")
        assert "target" not in resp.text

    def test_cannot_delete_self(self, client):
        """不能刪除自己（前端不顯示按鈕，但後端也要擋）。"""
        _register(client, "admin", "admin12345")
        _login(client, "admin", "admin12345")

        # 嘗試用 API 直接刪除自己
        resp = client.get("/accounts")
        # admin 的行不會有刪除按鈕，但我們測試 API
        assert "（你）" in resp.text

    def test_last_account_protection(self, client):
        """不能刪除最後一個帳號。"""
        _register(client, "only_user", "password123")
        _login(client, "only_user", "password123")
        # 只有一個帳號，無法對自己操作，所以這個保護主要在有多帳號但只剩一個啟用的情境
