# Quickstart: 使用者登入登出系統

> 本文件是實作導引，幫助開發者快速了解「要改哪些檔案」和「改的順序」。
> 【新手導讀】把這份文件當作你的「施工順序表」，一步一步來就不會迷路。

---

## 你需要認識的概念

在開始寫程式之前，先理解幾個核心概念：

### 1. 請求的生命週期（一個請求從頭到尾經歷了什麼）

```
使用者點擊按鈕或輸入網址
    │
    ▼
瀏覽器發出 HTTP 請求（例如 GET /meetings）
    │
    ▼
FastAPI 收到請求
    │
    ▼
FastAPI 根據「路由」（URL 路徑）找到對應的函式
    │
    ▼
如果函式有 Depends(...)，先執行依賴函式
    │  ← 這裡就是我們檢查登入狀態的地方！
    │
    ▼
執行路由函式（讀取資料庫、處理邏輯等）
    │
    ▼
回傳 HTML 頁面 或 JSON 資料給瀏覽器
```

### 2. 這個功能會動到的「層」

```
模板層（Templates）     ← 新增 login.html, register.html；修改 base.html
    ↕
路由層（Routes）        ← 新增 auth.py；修改 pages.py, meetings.py
    ↕
服務層（Services）      ← 新增 auth_service.py（密碼雜湊、驗證邏輯）
    ↕
資料模型層（Models）    ← 新增 User model；新增 Pydantic schemas
    ↕
資料庫層（Database）    ← 自動建表（SQLAlchemy 的 create_all）
```

---

## 實作步驟概覽

### Step 1：資料模型（打地基）

**要做什麼**：在資料庫裡建一張「使用者表」。

**要改的檔案**：
- `app/models/database_models.py` — 新增 `User` class
- `app/models/schemas.py` — 新增註冊/登入的 Pydantic model

**你會學到**：
- SQLAlchemy ORM 怎麼定義資料表
- Pydantic 怎麼定義「輸入資料的格式」

---

### Step 2：認證服務（核心邏輯）

**要做什麼**：寫一個專門處理「密碼雜湊」和「帳號驗證」的服務。

**要新增的檔案**：
- `app/services/auth_service.py` — 密碼雜湊、使用者建立、登入驗證

**你會學到**：
- 密碼雜湊的原理與使用方式
- 為什麼要把邏輯放在 service 層而不是直接寫在路由裡（分層架構）

---

### Step 3：Session 中間件（餐廳的號碼牌機制）

**要做什麼**：設定 Session 管理，讓伺服器可以「記住」誰已經登入。

**要改的檔案**：
- `app/main.py` — 加入 Session Middleware
- `app/dependencies.py` — 新增 `get_current_user` 依賴函式
- `pyproject.toml` — 新增套件依賴

**你會學到**：
- 什麼是 Middleware（中間件）
- Cookie 和 Session 的運作方式
- FastAPI 的 Depends() 依賴注入

---

### Step 4：路由（接線）

**要做什麼**：建立登入、註冊、登出的 URL 端點。

**要新增的檔案**：
- `app/api/routes/auth.py` — 認證相關路由

**要改的檔案**：
- `app/main.py` — 註冊新的路由
- `app/api/routes/pages.py` — 加上認證檢查
- `app/api/routes/meetings.py` — 加上認證檢查

**你會學到**：
- FastAPI 路由怎麼定義
- 表單處理（Form data）
- HTTP 重新導向（Redirect）

---

### Step 5：前端頁面（使用者看到的畫面）

**要做什麼**：建立登入頁和註冊頁的 HTML 模板。

**要新增的檔案**：
- `app/templates/login.html` — 登入頁面
- `app/templates/register.html` — 註冊頁面

**要改的檔案**：
- `app/templates/base.html` — 導覽列加上使用者名稱和登出按鈕

**你會學到**：
- Jinja2 模板的條件渲染（if/else）
- 表單的 HTML 結構
- Tailwind CSS 基本樣式

---

### Step 6：測試

**要做什麼**：確認所有功能都正常運作。

**要新增的檔案**：
- `tests/test_auth.py` — 認證功能的測試

**你會學到**：
- pytest 怎麼寫測試
- 怎麼測試 FastAPI 的路由

---

## 新增套件安裝指令

```bash0
# 在專案根目錄執行
uv add "passlib[bcrypt]" starlette-session
```

---

## 注意事項

1. **不要跳步驟** — 後面的步驟依賴前面的結果（例如沒有 User model 就不能寫認證邏輯）
2. **每做完一個步驟就測試** — 不要等到全部寫完才測，那時候出錯會很難找原因
3. **先跑通最簡單的流程** — 先讓「註冊 → 登入 → 看到首頁 → 登出」這條路走得通，再處理細節
