# Implementation Plan: 使用者登入登出系統

> 本文件是完整的技術實作計畫，從規格書（spec.md）翻譯成「怎麼做」。
> 【新手導讀】spec.md 說的是「要做什麼」，這份 plan.md 說的是「怎麼做」。

**Feature Branch**: `006-user-auth`
**Created**: 2026-03-27
**Status**: Ready for Tasks

---

## Technical Context（技術背景）

### 現有技術棧

| 項目 | 技術 | 說明 |
|------|------|------|
| 後端框架 | FastAPI | Python 的非同步 Web 框架 |
| 模板引擎 | Jinja2 | 伺服器端渲染 HTML |
| 前端互動 | HTMX | 用 HTML 屬性實現 AJAX，不需要寫 JavaScript 框架 |
| 前端樣式 | Tailwind CSS (CDN) | CSS 框架，用 class 名稱控制樣式 |
| ORM | SQLAlchemy (async) | 物件關聯映射，用 Python class 操作資料庫 |
| 資料庫 | SQLite (aiosqlite) | 輕量級的檔案型資料庫 |
| 套件管理 | uv | 快速的 Python 套件管理工具 |

### 新增技術

| 套件 | 版本 | 用途 |
|------|------|------|
| `passlib[bcrypt]` | latest | 密碼雜湊（把密碼變成不可逆的亂碼） |
| `starlette-session` | latest | Session 管理（記住使用者的登入狀態） |

---

## Constitution Check（專案守則檢查）

> 確認此計畫符合 constitution.md 中的所有規範。

| 守則 | 狀態 | 說明 |
|------|------|------|
| 模組化設計 / SRP | ✅ 符合 | 認證邏輯獨立為 auth_service.py，路由獨立為 auth.py |
| Docstring 規範 | ✅ 符合 | 所有新函式都會有 Google Style Docstring |
| 型別註解 | ✅ 符合 | 所有函式參數與回傳值都有 type hints |
| 命名慣例 | ✅ 符合 | snake_case 函式、PascalCase 類別 |
| 測試標準 | ✅ 符合 | 會新增 test_auth.py |
| 錯誤處理 | ✅ 符合 | 使用 HTTPException，統一錯誤回應格式 |
| 安全性 | ✅ 符合 | Session 密鑰使用環境變數，密碼雜湊存儲 |
| DI 模式 | ✅ 符合 | 使用 Depends() 注入認證依賴 |

---

## Architecture Overview（架構概覽）

### 新增/修改的檔案清單

```
app/
├── main.py                    ← 【修改】加入 Session Middleware
├── config.py                  ← 【修改】新增 SESSION_SECRET_KEY 設定
├── dependencies.py            ← 【修改】新增 get_current_user, get_current_user_optional
├── api/
│   └── routes/
│       ├── auth.py            ← 【新增】登入/註冊/登出路由
│       ├── pages.py           ← 【修改】所有頁面加上認證檢查
│       └── meetings.py        ← 【修改】所有 API 加上認證檢查
├── models/
│   ├── database_models.py     ← 【修改】新增 User model
│   └── schemas.py             ← 【修改】新增認證相關 Pydantic schemas
├── services/
│   └── auth_service.py        ← 【新增】密碼雜湊、使用者建立、登入驗證
├── templates/
│   ├── base.html              ← 【修改】導覽列加使用者名稱和登出按鈕
│   ├── login.html             ← 【新增】登入頁面
│   └── register.html          ← 【新增】註冊頁面
├── .env                       ← 【修改】新增 SESSION_SECRET_KEY
└── .env.example               ← 【修改】新增 SESSION_SECRET_KEY 範例
tests/
└── test_auth.py               ← 【新增】認證功能測試
pyproject.toml                 ← 【修改】新增套件依賴
```

### 資料流動圖（Data Flow）

> **這是最重要的概念**——了解資料從使用者的操作到資料庫，是怎麼一步一步傳遞的。

```
【登入流程】

1. 使用者在瀏覽器的登入頁面填寫帳號密碼
   ↓
2. 瀏覽器把表單資料以 POST 請求送到伺服器
   （資料格式：username=john&password=mypass123）
   ↓
3. FastAPI 的路由函式 login() 收到請求
   ↓
4. 路由函式呼叫 auth_service.authenticate_user(username, password)
   ↓
5. auth_service 去資料庫查找 username 對應的 User
   ↓
6. 找到後，用 passlib 比對密碼
   （把使用者輸入的密碼做一次雜湊，跟資料庫裡存的雜湊值比較）
   ↓
7. 比對成功 → 在 session 中存入 user_id 和 username
   ↓
8. 伺服器回傳 302 Redirect，瀏覽器跳轉到首頁
   （同時瀏覽器收到 Set-Cookie header，之後每次請求都會自動帶上這個 cookie）
```

```
【認證檢查流程（每次請求都會發生）】

1. 使用者訪問 /meetings
   ↓
2. 瀏覽器自動帶上 session cookie
   ↓
3. FastAPI 看到路由有 Depends(get_current_user)
   ↓
4. get_current_user 函式從 session 中讀取 user_id
   ↓
5a. 有 user_id → 回傳使用者資訊 → 路由函式正常執行
5b. 沒有 user_id → 頁面路由回傳 302 到 /login；API 路由回傳 401
```

---

## Implementation Phases（實作階段）

### Phase 1: 資料模型與基礎建設

**目標**：建立 User model、安裝套件、設定 Session。

**修改的檔案**：
1. `pyproject.toml` — 新增 `passlib[bcrypt]`、`starlette-session`
2. `app/models/database_models.py` — 新增 `User` class
3. `app/models/schemas.py` — 新增 `UserCreate`、`UserLogin` schemas
4. `app/config.py` — 新增 `SESSION_SECRET_KEY` 設定
5. `.env` / `.env.example` — 新增 `SESSION_SECRET_KEY`

**驗收標準**：
- `uv sync` 成功安裝套件
- 應用程式啟動後，資料庫自動建立 `users` 表

---

### Phase 2: 認證服務

**目標**：實作密碼雜湊和使用者驗證邏輯。

**新增的檔案**：
1. `app/services/auth_service.py`
   - `hash_password(password: str) -> str` — 密碼雜湊
   - `verify_password(plain: str, hashed: str) -> bool` — 密碼驗證
   - `create_user(db, username, password) -> User` — 建立使用者
   - `authenticate_user(db, username, password) -> User | None` — 登入驗證

**驗收標準**：
- 可以用 Python shell 測試密碼雜湊和驗證

---

### Phase 3: Session 中間件與認證依賴

**目標**：設定 Session 管理，建立認證檢查的依賴函式。

**修改的檔案**：
1. `app/main.py` — 加入 `SessionMiddleware`
2. `app/dependencies.py` — 新增：
   - `get_current_user(request) -> dict` — 從 session 取得使用者（未登入則導向/拒絕）
   - `get_current_user_optional(request) -> dict | None` — 同上但允許未登入（用於公開頁面）

**驗收標準**：
- Session middleware 正常運作
- 未登入訪問受保護路由被導向 /login

---

### Phase 4: 認證路由

**目標**：建立登入、註冊、登出的端點。

**新增的檔案**：
1. `app/api/routes/auth.py` — 所有認證路由

**修改的檔案**：
1. `app/main.py` — 註冊 auth router

**路由清單**：
- `GET /register` — 顯示註冊頁
- `POST /register` — 處理註冊
- `GET /login` — 顯示登入頁
- `POST /login` — 處理登入
- `POST /logout` — 登出

**驗收標準**：
- 可以完成註冊 → 登入 → 登出的完整流程

---

### Phase 5: 保護現有路由

**目標**：為所有現有頁面和 API 加上認證檢查。

**修改的檔案**：
1. `app/api/routes/pages.py` — 所有頁面路由加 `Depends(get_current_user)`
2. `app/api/routes/meetings.py` — 所有 API 路由加 `Depends(get_current_user)`

**驗收標準**：
- 未登入訪問 `/` → 被導向 `/login`
- 未登入呼叫 `/api/meetings` → 收到 401
- 登入後訪問 `/meetings` → 正常顯示

---

### Phase 6: 前端頁面

**目標**：建立登入/註冊頁面，修改導覽列。

**新增的檔案**：
1. `app/templates/login.html` — 登入頁面（帳號、密碼輸入框、錯誤訊息、「前往註冊」連結）
2. `app/templates/register.html` — 註冊頁面（帳號、密碼輸入框、錯誤訊息、「前往登入」連結）

**修改的檔案**：
1. `app/templates/base.html` — 導覽列右側顯示使用者名稱和登出按鈕

**驗收標準**：
- 登入/註冊頁面樣式與現有頁面一致（Tailwind）
- 錯誤訊息正確顯示
- session 過期時顯示提示訊息

---

### Phase 7: 測試

**目標**：確認所有功能正常。

**新增的檔案**：
1. `tests/test_auth.py`

**測試案例**：
- 註冊成功
- 註冊重複帳號失敗
- 登入成功
- 登入錯誤密碼失敗
- 登出成功
- 未登入訪問受保護頁面被導向
- 未登入呼叫 API 收到 401

**驗收標準**：
- 所有測試通過

---

## Design Artifacts（設計文件）

| 文件 | 路徑 | 說明 |
|------|------|------|
| 規格書 | `specs/006-user-auth/spec.md` | 功能需求（做什麼） |
| 研究紀錄 | `specs/006-user-auth/research.md` | 技術決策（為什麼這樣選） |
| 資料模型 | `specs/006-user-auth/data-model.md` | 資料表設計 |
| API 合約 | `specs/006-user-auth/contracts/api-endpoints.md` | 端點定義 |
| 快速導引 | `specs/006-user-auth/quickstart.md` | 施工順序表 |
| 品質檢查 | `specs/006-user-auth/checklists/requirements.md` | 規格品質檢查 |

---

## Risk Assessment（風險評估）

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| starlette-session 與現有 HTMX 衝突 | 中 | 先裝套件測試基本功能再繼續 |
| 資料庫 migration（既有資料表結構變更） | 低 | 只新增 users 表，不修改現有表 |
| Session 重啟後丟失 | 低 | v1 可接受，記錄為已知限制 |
| 密碼安全性不足 | 高 | 使用 bcrypt（業界標準），不自己實作 |
