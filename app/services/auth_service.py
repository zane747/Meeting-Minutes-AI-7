"""認證服務：密碼雜湊、使用者建立、登入驗證。

【新手導讀】這個檔案是認證功能的「核心邏輯層」（Service Layer）。
為什麼不直接把邏輯寫在路由裡？因為「分層架構」的原則：
- 路由（Route）負責「接收請求、回傳回應」
- 服務（Service）負責「商業邏輯」（密碼雜湊、驗證等）
- 模型（Model）負責「資料結構」

這樣做的好處：如果以後要改密碼雜湊演算法（例如從 bcrypt 換成 argon2），
只需要改這個檔案，路由的程式碼完全不用動。

術語解釋：
- hash（雜湊）：把密碼變成一串看起來像亂碼的字串，而且無法反推回原始密碼。
- verify（驗證）：把使用者輸入的密碼做一次雜湊，跟資料庫裡存的比較是否一致。
- bcrypt：一種專為密碼設計的雜湊演算法，自動加「鹽值」（salt），很安全。
"""

import logging

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database_models import User

logger = logging.getLogger(__name__)

# === 密碼雜湊設定 ===
# 直接使用 bcrypt 套件（比 passlib 更簡單直接）。
# bcrypt.gensalt() 會自動產生隨機的「鹽值」（salt），
# 確保即使兩個使用者用同樣的密碼，雜湊結果也不同。


def hash_password(password: str) -> str:
    """將明文密碼雜湊為不可逆的字串。

    【新手導讀】這個函式就像「碎紙機」：
    輸入 "mypassword123" → 輸出 "$2b$12$LJ3m4ks..." （一串亂碼）
    每次呼叫的輸出都不同（因為 bcrypt 自動加隨機鹽值），但都能用來驗證。

    Args:
        password: 使用者輸入的原始密碼。

    Returns:
        bcrypt 雜湊後的字串（約 60 個字元）。
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """比對明文密碼與雜湊值是否匹配。

    【新手導讀】這個函式的運作方式：
    1. 把 plain_password 用同樣的方式做一次雜湊
    2. 跟 hashed_password（資料庫裡存的）比較
    3. 一樣就回傳 True，不一樣就回傳 False

    Args:
        plain_password: 使用者輸入的原始密碼。
        hashed_password: 資料庫中儲存的雜湊值。

    Returns:
        True 表示密碼正確，False 表示密碼錯誤。
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:
    """建立新使用者（密碼會自動雜湊後儲存）。

    【新手導讀】這個函式做了三件事：
    1. 把密碼丟進碎紙機（hash_password）
    2. 建立一個 User 物件（SQLAlchemy 會對應到資料庫的一行資料）
    3. 存入資料庫（db.add → db.commit → db.refresh）

    Args:
        db: 資料庫 Session（由 FastAPI 的 Depends 注入）。
        username: 帳號名稱。
        password: 原始密碼（會被雜湊後才存入）。

    Returns:
        新建立的 User 物件（包含自動生成的 id）。
    """
    hashed = hash_password(password)
    user = User(username=username, password_hash=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"新使用者註冊：{username}")
    return user


async def get_user_by_username(
    db: AsyncSession,
    username: str,
) -> User | None:
    """根據帳號名稱查詢使用者。

    Args:
        db: 資料庫 Session。
        username: 要查詢的帳號名稱。

    Returns:
        找到的 User 物件，找不到則回傳 None。
    """
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    """驗證使用者的帳號密碼是否正確。

    【新手導讀】這是登入時呼叫的核心函式，流程如下：
    1. 用 username 去資料庫查找使用者
    2. 找不到 → 回傳 None（登入失敗）
    3. 找到了 → 用 verify_password 比對密碼
    4. 密碼正確 → 回傳 User 物件（登入成功）
    5. 密碼錯誤 → 回傳 None（登入失敗）

    注意：不管是「帳號不存在」還是「密碼錯誤」，都回傳 None。
    這是安全考量——如果分開處理，攻擊者就能知道某個帳號是否存在（帳號枚舉攻擊）。

    Args:
        db: 資料庫 Session。
        username: 使用者輸入的帳號。
        password: 使用者輸入的密碼。

    Returns:
        驗證成功回傳 User 物件，失敗回傳 None。
    """
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# === 帳號管理功能（007-account-management 新增）===


async def get_all_users(db: AsyncSession) -> list[User]:
    """取得所有使用者列表（依建立時間倒序）。

    Args:
        db: 資料庫 Session。

    Returns:
        使用者列表。
    """
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_active_user_count(db: AsyncSession) -> int:
    """取得目前啟用狀態的帳號數量。

    用於保護「至少一個啟用帳號」的規則：
    停用或刪除前先查這個數字，如果只剩 1 就拒絕操作。

    Args:
        db: 資料庫 Session。

    Returns:
        啟用帳號數量。
    """
    result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    return result.scalar_one()


async def change_password(
    db: AsyncSession,
    user_id: str,
    old_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """修改使用者密碼。

    流程：查找使用者 → 驗證舊密碼 → 雜湊新密碼 → 更新資料庫。

    Args:
        db: 資料庫 Session。
        user_id: 要修改密碼的使用者 ID。
        old_password: 使用者輸入的舊密碼。
        new_password: 使用者輸入的新密碼。

    Returns:
        (成功與否, 訊息) 的 tuple。
    """
    user = await db.get(User, user_id)
    if not user:
        return False, "使用者不存在"

    if not verify_password(old_password, user.password_hash):
        return False, "舊密碼不正確"

    if len(new_password) < 8:
        return False, "新密碼長度至少 8 個字元"

    user.password_hash = hash_password(new_password)
    await db.commit()
    logger.info(f"使用者修改密碼：{user.username}")
    return True, "密碼修改成功"


async def toggle_user_active(
    db: AsyncSession,
    user_id: str,
    operator_id: str,
) -> tuple[bool, str]:
    """切換帳號的啟用/停用狀態。

    保護規則：
    - 不能操作自己的帳號
    - 停用後至少要有一個啟用帳號

    Args:
        db: 資料庫 Session。
        user_id: 要操作的帳號 ID。
        operator_id: 執行操作的使用者 ID（用來檢查是不是自己）。

    Returns:
        (成功與否, 訊息) 的 tuple。
    """
    if user_id == operator_id:
        return False, "無法停用自己的帳號"

    user = await db.get(User, user_id)
    if not user:
        return False, "帳號不存在"

    # 如果要停用（目前是啟用），檢查是不是最後一個啟用帳號
    if user.is_active:
        active_count = await get_active_user_count(db)
        if active_count <= 1:
            return False, "系統至少需要一個啟用帳號"

    # 切換狀態
    user.is_active = not user.is_active
    await db.commit()

    status = "啟用" if user.is_active else "停用"
    logger.info(f"帳號 {user.username} 已被{status}")
    return True, f"帳號已{status}"


async def delete_user(
    db: AsyncSession,
    user_id: str,
    operator_id: str,
) -> tuple[bool, str]:
    """刪除帳號。

    保護規則：
    - 不能刪除自己
    - 系統至少保留一個帳號

    Args:
        db: 資料庫 Session。
        user_id: 要刪除的帳號 ID。
        operator_id: 執行操作的使用者 ID。

    Returns:
        (成功與否, 訊息) 的 tuple。
    """
    if user_id == operator_id:
        return False, "無法刪除自己的帳號"

    user = await db.get(User, user_id)
    if not user:
        return False, "帳號不存在"

    # 如果這是啟用帳號，確保刪除後至少還有一個啟用帳號
    if user.is_active:
        active_count = await get_active_user_count(db)
        if active_count <= 1:
            return False, "系統至少需要一個啟用帳號"

    username = user.username
    await db.delete(user)
    await db.commit()
    logger.info(f"帳號已刪除：{username}")
    return True, "帳號已刪除"
