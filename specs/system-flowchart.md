# Meeting Minutes AI — 系統流程圖

> 用圖解方式說明整個系統的運作流程。對照程式碼時可以用這份圖當地圖。

---

## 一、系統啟動流程

**對應檔案：`app/main.py`**

```
雙擊 start.bat 或執行 uvicorn app.main:app --reload
    │
    ▼
┌─────────────────────────────────────────────┐
│  FastAPI app 建立                            │
│  app = FastAPI(title="Meeting Minutes AI")  │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  加入 SessionMiddleware                      │
│  （讓伺服器能「記住」使用者的登入狀態）        │
│  設定：secret_key、cookie_name、max_age      │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  掛載靜態資源 /static                        │
│  （CSS、JS 等檔案讓瀏覽器能下載）             │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  註冊路由（順序重要！）                       │
│  1. auth.router    → /login, /register...   │
│  2. meetings.router → /api/meetings/...     │
│  3. pages.router   → /, /meetings/...       │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  lifespan 啟動事件                           │
│  1. init_db() → 建立資料庫表格               │
│  2. mkdir uploads/ → 建立上傳目錄            │
│  3. health_check() → 檢查 AI Provider 可用   │
└─────────────────────────────────────────────┘
    │
    ▼
  伺服器開始監聽 http://localhost:8000
```

---

## 二、每一次 HTTP 請求的生命週期

**使用者的每個操作（點連結、送表單、呼叫 API）都會經過這個流程**

```
使用者操作（點按鈕、輸入網址）
    │
    ▼
瀏覽器發出 HTTP 請求（例如 GET /meetings）
    │
    ▼
┌──────────────────────────────────┐
│  SessionMiddleware                │ ← app/main.py 設定的
│  從 Cookie 讀取 session ID        │
│  載入 session 資料到 request       │
│  （如果有的話）                    │
└──────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────┐
│  FastAPI 路由匹配                 │
│  根據 URL + HTTP 方法             │
│  找到對應的路由函式                │
│  例如 GET /meetings → pages.py    │
└──────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────┐
│  依賴注入（Depends）              │ ← app/dependencies.py
│  路由函式執行「之前」先跑這些：    │
│  • get_current_user → 檢查登入   │
│  • get_db → 取得資料庫連線        │
│  如果依賴失敗 → 直接回傳錯誤      │
│  路由函式根本不會被執行            │
└──────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────┐
│  路由函式執行                     │ ← app/api/routes/*.py
│  • 呼叫服務層處理業務邏輯         │
│  • 查詢/寫入資料庫               │
│  • 渲染模板 或 組裝 JSON         │
└──────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────┐
│  SessionMiddleware（回程）        │
│  如果 session 有變動              │
│  → 加密後寫入 Set-Cookie header  │
└──────────────────────────────────┘
    │
    ▼
瀏覽器收到回應（HTML 頁面 或 JSON 資料）
```

---

## 三、認證流程

### 3a. 註冊

**對應檔案：`auth.py` → `auth_service.py` → `database_models.py`**

```
使用者填帳號密碼 → 按「註冊」
    │
    ▼
POST /register
    │
    ▼
┌─ auth.py ─────────────────────────────┐
│                                        │
│  驗證帳號格式（3~30字，英數字底線）     │
│      ↓ 失敗 → 重新顯示註冊頁+錯誤訊息  │
│                                        │
│  驗證密碼長度（≥8）                     │
│      ↓ 失敗 → 重新顯示註冊頁+錯誤訊息  │
│                                        │
│  呼叫 auth_service ↓                   │
└────────────────────│───────────────────┘
                     │
                     ▼
┌─ auth_service.py ──────────────────────┐
│                                        │
│  get_user_by_username()                │
│  → 查資料庫，帳號是否已存在？           │
│      ↓ 已存在 → 回傳錯誤              │
│                                        │
│  create_user()                         │
│  → bcrypt 雜湊密碼                     │
│  → 建立 User 物件                      │
│  → db.add() + db.commit()             │
│  → 存入資料庫                          │
│                                        │
└────────────────────│───────────────────┘
                     │
                     ▼
┌─ auth.py（繼續）──────────────────────┐
│                                       │
│  request.session["user_id"] = user.id │
│  request.session["username"] = ...    │
│  （建立 session = 自動登入）           │
│                                       │
│  302 Redirect → /（跳轉首頁）         │
│                                       │
└───────────────────────────────────────┘
```

### 3b. 登入

**對應檔案：`auth.py` → `auth_service.py`**

```
使用者填帳號密碼 → 按「登入」
    │
    ▼
POST /login
    │
    ▼
┌─ auth.py ──────────────────────────────┐
│                                         │
│  呼叫 auth_service.authenticate_user() │
│                                         │
└──────────────────│──────────────────────┘
                   │
                   ▼
┌─ auth_service.py ──────────────────────┐
│                                        │
│  ① get_user_by_username(username)     │
│     → 去資料庫找這個帳號              │
│     → 找不到 → 回傳 None             │
│                                        │
│  ② verify_password(輸入的密碼, 資料庫的雜湊值)│
│     → bcrypt 比對                     │
│     → 不符合 → 回傳 None             │
│                                        │
│  ③ 都通過 → 回傳 User 物件           │
│                                        │
└──────────────────│──────────────────────┘
                   │
                   ▼
┌─ auth.py（繼續）──────────────────────┐
│                                       │
│  如果 User 是 None:                   │
│    → 顯示「帳號或密碼錯誤」           │
│    （不區分哪個錯，防止帳號枚舉攻擊）  │
│                                       │
│  如果成功:                            │
│    → session 存入使用者資訊           │
│    → 302 導向 next 或首頁             │
│                                       │
└───────────────────────────────────────┘
```

### 3c. 認證檢查（每個受保護頁面都會走這個）

**對應檔案：`dependencies.py`**

```
使用者訪問任何受保護頁面（例如 GET /meetings）
    │
    ▼
FastAPI 看到路由有 Depends(get_current_user)
    │
    ▼
┌─ dependencies.py ─────────────────────┐
│                                       │
│  get_current_user(request)            │
│                                       │
│  從 request.session 讀取 user_id      │
│       │                               │
│       ├── 有 user_id                  │
│       │   → 回傳 {user_id, username}  │
│       │   → 路由函式正常執行          │
│       │                               │
│       └── 沒有 user_id（未登入）      │
│           │                           │
│           ├── 網址以 /api/ 開頭       │
│           │   → 回傳 401 JSON 錯誤    │
│           │                           │
│           └── 一般頁面                │
│               → 302 導向 /login       │
│               → 帶上 ?next= 原網址    │
│                                       │
└───────────────────────────────────────┘
```

### 3d. 登出

**對應檔案：`auth.py`**

```
使用者按「登出」按鈕（<form method="post"> 送出）
    │
    ▼
POST /logout
    │
    ▼
┌─ auth.py ─────────────────────────────┐
│                                       │
│  Depends(get_current_user)            │
│  → 確認使用者已登入（沒登入會被擋）    │
│                                       │
│  request.session.clear()              │
│  → 清空 session（伺服器忘記你是誰）    │
│                                       │
│  302 Redirect → /login                │
│                                       │
└───────────────────────────────────────┘
```

---

## 四、會議處理流程（核心功能）

**對應檔案：`meetings.py` → `audio_service.py` → `meeting_processor.py` → `providers/`**

```
使用者選擇音檔 → 按「上傳並處理」
    │
    ▼
POST /api/meetings/upload-and-process
    │
    ▼
┌─ meetings.py ─────────────────────────┐
│                                       │
│  Depends(get_current_user) → 確認登入 │
│                                       │
└──────────────────│────────────────────┘
                   │
                   ▼
┌─ audio_service.py ────────────────────┐
│                                       │
│  validate_audio_file()                │
│  → 檢查格式（mp3/wav/flac）          │
│  → 檢查大小（≤ 300MB）               │
│  → 失敗 → 400 錯誤                   │
│                                       │
│  save_file()                          │
│  → 存到 uploads/ 目錄                │
│                                       │
└──────────────────│────────────────────┘
                   │
                   ▼
┌─ meetings.py（繼續）──────────────────┐
│                                       │
│  建立 Meeting 記錄                    │
│  → status = PROCESSING               │
│  → 存入資料庫                         │
│                                       │
│  丟到背景任務 ↓                       │
│  （使用者不用等，可以做其他事）        │
│                                       │
└──────────────────│────────────────────┘
                   │
    ┌──────────────┴──────────────┐
    │         背景任務              │
    │                              │
    ▼                              │
┌─ meeting_processor.py ──────┐   │
│                              │   │
│  根據 mode 選擇 Provider:   │   │
│                              │   │
│  remote → GeminiProvider    │   │  使用者這時候
│  local  → WhisperProvider   │   │  可以做其他事
│                              │   │
│  provider.process(音檔路徑) │   │
│  → 產出逐字稿 + 摘要        │   │
│  → 產出 Action Items        │   │
│                              │   │
│  更新 Meeting 記錄           │   │
│  → transcript = 逐字稿      │   │
│  → summary = 摘要            │   │
│  → status = COMPLETED        │   │
│                              │   │
│  失敗的話:                   │   │
│  → status = FAILED           │   │
│  → error_message = 錯誤原因  │   │
│                              │   │
└──────────────────────────────┘   │
    └──────────────────────────────┘
                   │
                   ▼
┌─ 前端（HTMX 輪詢）──────────────────┐
│                                       │
│  每 2 秒發一次:                       │
│  GET /api/meetings/{id}/status        │
│                                       │
│  status = PROCESSING → 繼續等         │
│  status = COMPLETED  → 跳轉結果頁    │
│  status = FAILED     → 顯示錯誤      │
│                                       │
└───────────────────────────────────────┘
```

---

## 五、分層架構總覽

```
┌─────────────────────────────────────────────────────────┐
│                     使用者（瀏覽器）                      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP 請求/回應
                         ▼
┌─────────────────────────────────────────────────────────┐
│  模板層 Templates                                        │
│  app/templates/*.html                                    │
│  負責：畫面長什麼樣子                                     │
│  工具：Jinja2 + Tailwind CSS + HTMX                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  路由層 Routes                                           │
│  app/api/routes/auth.py, pages.py, meetings.py          │
│  負責：接收請求 → 呼叫服務層 → 回傳回應                   │
│  工具：FastAPI Router, Depends()                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  依賴層 Dependencies                                     │
│  app/dependencies.py                                     │
│  負責：認證檢查、Provider 選擇                            │
│  工具：FastAPI Depends()                                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  服務層 Services                                         │
│  app/services/auth_service.py, audio_service.py, ...    │
│  負責：業務邏輯（密碼雜湊、音檔處理、AI 呼叫）            │
│  工具：bcrypt, pydub, Gemini API, Whisper               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  資料層 Models                                           │
│  app/models/database_models.py, schemas.py              │
│  負責：資料結構定義、格式驗證                              │
│  工具：SQLAlchemy ORM, Pydantic                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  資料庫 Database                                         │
│  meeting_minutes.db (SQLite)                             │
│  表：users, meetings, action_items, annotation_files    │
└─────────────────────────────────────────────────────────┘
```

---

## 六、檔案 vs 職責 快速對照

| 我要找... | 去看哪個檔案 |
|----------|-------------|
| 系統啟動時做了什麼 | `app/main.py` |
| 環境變數設定 | `app/config.py` → `.env` |
| 資料庫連線怎麼建立 | `app/database.py` |
| 怎麼判斷使用者有沒有登入 | `app/dependencies.py` |
| 登入/註冊/登出的流程 | `app/api/routes/auth.py` |
| 頁面路由（首頁、歷史、會議詳情） | `app/api/routes/pages.py` |
| 會議 API（上傳、CRUD） | `app/api/routes/meetings.py` |
| 密碼雜湊和驗證 | `app/services/auth_service.py` |
| 音檔上傳和驗證 | `app/services/audio_service.py` |
| AI 處理（背景任務） | `app/services/meeting_processor.py` |
| Gemini API 怎麼呼叫 | `app/services/providers/gemini_provider.py` |
| Whisper 本地轉錄 | `app/services/providers/local_whisper_provider.py` |
| 資料庫有哪些表 | `app/models/database_models.py` |
| API 請求/回應格式 | `app/models/schemas.py` |
| 頁面長什麼樣 | `app/templates/*.html` |
