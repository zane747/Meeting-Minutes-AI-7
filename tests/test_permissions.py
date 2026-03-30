"""權限管理功能測試。"""

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
    from app.main import app
    with TestClient(app) as c:
        yield c


def _register(client, username="admin", password="admin12345"):
    return client.post("/register", data={"username": username, "password": password}, follow_redirects=False)


def _login(client, username="admin", password="admin12345"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=False)


def _get_user_id(client, target_username):
    """從帳號列表頁面取得使用者 ID。"""
    import re
    resp = client.get("/accounts")
    match = re.search(rf"toggleActive\('([^']+)', '{target_username}'\)", resp.text)
    if match:
        return match.group(1)
    # 也試試 deleteUser
    match = re.search(rf"deleteUser\('([^']+)', '{target_username}'\)", resp.text)
    if match:
        return match.group(1)
    return None


# === 角色自動分配 ===


class TestAutoRole:
    def test_first_user_is_admin(self, client):
        """第一個註冊的帳號自動成為等級 1。"""
        _register(client, "first_user", "password123")
        resp = client.get("/accounts")
        assert resp.status_code == 200
        assert "超級管理員" in resp.text

    def test_second_user_is_normal(self, client):
        """後續帳號預設為等級 3。"""
        _register(client, "first_user", "password123")
        # 登出再用另一個帳號註冊
        client.post("/logout", follow_redirects=False)
        _register(client, "second_user", "password123")
        # 用 first_user 登入看帳號列表
        client.post("/logout", follow_redirects=False)
        _login(client, "first_user", "password123")
        resp = client.get("/accounts")
        assert "一般使用者" in resp.text


# === 權限控制 ===


class TestPermissions:
    def test_level3_cannot_access_accounts(self, client):
        """等級 3 無法訪問帳號管理。"""
        _register(client, "admin_user", "password123")
        client.post("/logout", follow_redirects=False)
        _register(client, "normal_user", "password123")
        # normal_user 是等級 3
        resp = client.get("/accounts")
        assert resp.status_code == 403

    def test_level3_cannot_access_admin(self, client):
        """等級 3 無法訪問管理中心。"""
        _register(client, "admin_user", "password123")
        client.post("/logout", follow_redirects=False)
        _register(client, "normal_user", "password123")
        resp = client.get("/admin")
        assert resp.status_code == 403

    def test_level1_can_access_admin(self, client):
        """等級 1 可以訪問管理中心。"""
        _register(client, "admin_user", "password123")
        resp = client.get("/admin")
        assert resp.status_code == 200
        assert "管理中心" in resp.text


# === 角色變更 ===


class TestRoleChange:
    def test_change_role_to_admin(self, client):
        """等級 1 可以把等級 3 升為等級 2。"""
        _register(client, "super_admin", "password123")
        client.post("/logout", follow_redirects=False)
        _register(client, "target_user", "password123")
        client.post("/logout", follow_redirects=False)
        _login(client, "super_admin", "password123")

        target_id = _get_user_id(client, "target_user")
        assert target_id is not None

        resp = client.post(
            f"/api/accounts/{target_id}/change-role",
            json={"role": 2},
        )
        assert resp.status_code == 200

    def test_level3_cannot_change_role(self, client):
        """等級 3 不能變更角色（API 直接 403）。"""
        _register(client, "super_admin", "password123")
        client.post("/logout", follow_redirects=False)
        _register(client, "normal_user", "password123")

        # normal_user 嘗試呼叫 change-role API
        resp = client.post(
            "/api/accounts/fake-id/change-role",
            json={"role": 2},
        )
        assert resp.status_code == 403


# === 停用帳號登入提示 ===


class TestDeactivatedLogin:
    def test_deactivated_shows_specific_message(self, client):
        """被停用帳號登入顯示「帳號已被停用」。"""
        _register(client, "admin_user", "password123")
        client.post("/logout", follow_redirects=False)
        _register(client, "target_user", "password123")
        client.post("/logout", follow_redirects=False)
        _login(client, "admin_user", "password123")

        target_id = _get_user_id(client, "target_user")
        assert target_id is not None
        client.post(f"/api/accounts/{target_id}/toggle-active")

        # 登出 admin，嘗試用被停用帳號登入
        client.post("/logout", follow_redirects=False)
        resp = _login(client, "target_user", "password123")
        assert resp.status_code == 200
        assert "帳號已被停用" in resp.text

    def test_nonexistent_shows_generic_message(self, client):
        """不存在的帳號仍顯示通用錯誤。"""
        resp = client.post(
            "/login",
            data={"username": "no_such_user", "password": "whatever123"},
        )
        assert "帳號或密碼錯誤" in resp.text
