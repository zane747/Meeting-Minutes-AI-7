# Implementation Plan: 帳號管理

**Feature Branch**: `007-account-management`
**Created**: 2026-03-30
**Status**: Ready for Tasks

---

## Technical Context

### 沿用技術棧

與 006-user-auth 完全相同（FastAPI + Jinja2 + SQLAlchemy + HTMX + Tailwind）。
不需要新增任何套件。

---

## Constitution Check

| 守則 | 狀態 | 說明 |
|------|------|------|
| 模組化設計 / SRP | ✅ | 帳號管理路由獨立為 accounts.py，密碼修改邏輯在 auth_service |
| Docstring 規範 | ✅ | 所有新函式都會有 Google Style Docstring |
| 型別註解 | ✅ | 所有函式參數與回傳值都有 type hints |
| 命名慣例 | ✅ | snake_case 函式、PascalCase 類別 |
| 測試標準 | ✅ | 會新增 test_accounts.py |
| 錯誤處理 | ✅ | 使用 HTTPException，統一錯誤格式 |
| 安全性 | ✅ | 舊密碼驗證、不能操作自己、最後帳號保護 |

---

## Architecture Overview

### 新增/修改的檔案

```
app/
├── dependencies.py            ← 【修改】get_current_user 加入 is_active 檢查
├── api/routes/
│   └── accounts.py            ← 【新增】帳號管理路由
├── main.py                    ← 【修改】註冊 accounts router
├── services/
│   └── auth_service.py        ← 【修改】新增 change_password、toggle_active、delete_user 函式
├── templates/
│   ├── base.html              ← 【修改】導覽列加「帳號管理」和「修改密碼」連結
│   ├── accounts.html          ← 【新增】帳號列表頁面
│   └── change_password.html   ← 【新增】修改密碼頁面
tests/
└── test_accounts.py           ← 【新增】帳號管理測試
```

### 資料流

```
【帳號列表】
GET /accounts → accounts.py → 查詢所有 User → 渲染 accounts.html

【修改密碼】
POST /accounts/change-password → accounts.py → auth_service.change_password()
    → verify_password(舊密碼) → hash_password(新密碼) → 更新資料庫

【停用/啟用】
POST /api/accounts/{id}/toggle-active → accounts.py → auth_service.toggle_active()
    → 檢查不是自己 → 檢查至少一個啟用帳號 → 切換 is_active → 回傳 JSON

【刪除】
DELETE /api/accounts/{id} → accounts.py → auth_service.delete_user()
    → 檢查不是自己 → 檢查至少一個帳號 → 刪除 → 回傳 JSON

【被停用帳號的強制登出】
任何請求 → get_current_user() → 用 user_id 查資料庫
    → is_active=False → 清除 session → 導向 /login
```

---

## Implementation Phases

### Phase 1: 服務層擴充

**修改的檔案**：`app/services/auth_service.py`

新增函式：
- `change_password(db, user_id, old_password, new_password)` — 修改密碼
- `toggle_user_active(db, user_id, operator_id)` — 停用/啟用帳號
- `delete_user(db, user_id, operator_id)` — 刪除帳號
- `get_all_users(db)` — 取得所有使用者列表
- `get_active_user_count(db)` — 取得啟用帳號數量

### Phase 2: 依賴層修改

**修改的檔案**：`app/dependencies.py`

修改 `get_current_user()`：加入從資料庫查詢 `is_active` 的檢查。

### Phase 3: 路由與頁面

**新增的檔案**：
- `app/api/routes/accounts.py` — 帳號管理路由
- `app/templates/accounts.html` — 帳號列表頁面
- `app/templates/change_password.html` — 修改密碼頁面

**修改的檔案**：
- `app/main.py` — 註冊 accounts router
- `app/templates/base.html` — 導覽列加連結

### Phase 4: 測試

**新增的檔案**：`tests/test_accounts.py`

---

## Risk Assessment

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| get_current_user 加 DB 查詢增加每次請求延遲 | 低 | SQLite 本地查詢 < 1ms |
| 停用帳號但 session 未立即失效 | 低 | 下次請求就會被擋，延遲最多幾秒 |
| 誤刪最後一個帳號 | 高 | 後端 COUNT 檢查 + 前端二次確認 |
