# API Contracts: 使用者登入登出系統

> 本文件定義此功能新增和修改的 API 端點（Endpoints）。
> 【新手導讀】API 就像餐廳的菜單——定義了「你可以點什麼」以及「會得到什麼」。
> 每個端點就是一道菜，有固定的「點法」（請求格式）和「上菜方式」（回應格式）。

---

## 新增端點

### 1. 顯示註冊頁面

> 使用者在瀏覽器輸入網址，伺服器「渲染」（render）一個 HTML 頁面回傳給瀏覽器顯示。
> GET 就是「拿東西」的意思——瀏覽器說「給我這個頁面」。

```
GET /register
```

| 項目 | 說明 |
|------|------|
| 用途 | 顯示註冊表單頁面 |
| 認證 | ❌ 不需要（公開頁面） |
| 回應 | HTML 頁面（Jinja2 渲染的 register.html） |

---

### 2. 處理註冊表單

> 使用者填好表單按下「註冊」按鈕，瀏覽器把表單資料「POST」到伺服器。
> POST 就是「送東西」的意思——瀏覽器說「這是我的資料，幫我處理」。

```
POST /register
```

| 項目 | 說明 |
|------|------|
| 用途 | 處理使用者註冊 |
| 認證 | ❌ 不需要 |
| Content-Type | `application/x-www-form-urlencoded`（標準 HTML 表單格式） |

**請求欄位（表單）**:

| 欄位 | 型別 | 必填 | 驗證 |
|------|------|------|------|
| `username` | string | 是 | 3~30 字元，英數字與底線 |
| `password` | string | 是 | 至少 8 字元 |

**回應（成功）**:
- 302 Redirect → `/`（重新導向到首頁）
- 同時建立 session cookie

**回應（失敗）**:
- 200 OK + 重新渲染 register.html（帶錯誤訊息）
- 錯誤情境：帳號已存在、格式不符、密碼太短

---

### 3. 顯示登入頁面

```
GET /login
```

| 項目 | 說明 |
|------|------|
| 用途 | 顯示登入表單頁面 |
| 認證 | ❌ 不需要（公開頁面） |
| 回應 | HTML 頁面（Jinja2 渲染的 login.html） |

**Query Parameters（網址參數）**:

| 參數 | 說明 | 範例 |
|------|------|------|
| `next` | 登入後要導回的頁面路徑 | `/login?next=/meetings/abc` |
| `expired` | 是否因 session 過期被導向 | `/login?expired=1` |

---

### 4. 處理登入表單

```
POST /login
```

| 項目 | 說明 |
|------|------|
| 用途 | 驗證帳號密碼並建立 session |
| 認證 | ❌ 不需要 |
| Content-Type | `application/x-www-form-urlencoded` |

**請求欄位（表單）**:

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `username` | string | 是 | 帳號 |
| `password` | string | 是 | 密碼 |

**隱藏欄位**:

| 欄位 | 說明 |
|------|------|
| `next` | 從 query parameter 帶入，登入成功後的導向目標 |

**回應（成功）**:
- 302 Redirect → `next` 參數指定的路徑，或預設 `/`
- 設定 session cookie

**回應（失敗）**:
- 200 OK + 重新渲染 login.html（帶「帳號或密碼錯誤」訊息）
- 注意：不會告訴使用者「是帳號錯還是密碼錯」（安全考量，防止帳號枚舉）

---

### 5. 登出

```
POST /logout
```

| 項目 | 說明 |
|------|------|
| 用途 | 清除使用者的 session，登出系統 |
| 認證 | ✅ 需要（必須已登入） |
| 回應 | 302 Redirect → `/login` |

> **為什麼登出用 POST 而不是 GET？**
> 安全考量！如果登出用 GET，有人可以在網頁裡放一個 `<img src="/logout">`，
> 你只要打開那個頁面就會被強制登出（這叫 CSRF 攻擊）。
> 用 POST 搭配表單送出，可以避免這種問題。

---

## 修改的端點

### 所有現有的受保護端點

> 以下是目前已存在的端點，它們需要加上「認證檢查」：
> 如果使用者沒有登入，就不能使用這些功能。

**頁面路由（加上認證依賴）**:

| 端點 | 修改內容 |
|------|---------|
| `GET /` | 未登入 → 302 重導到 `/login` |
| `GET /meetings` | 未登入 → 302 重導到 `/login?next=/meetings` |
| `GET /meetings/{id}` | 未登入 → 302 重導到 `/login?next=/meetings/{id}` |

**API 路由（加上認證依賴）**:

| 端點 | 修改內容 |
|------|---------|
| `POST /api/meetings/upload-and-process` | 未登入 → 401 Unauthorized |
| `GET /api/meetings` | 未登入 → 401 Unauthorized |
| `GET /api/meetings/{id}` | 未登入 → 401 Unauthorized |
| `PUT /api/meetings/{id}` | 未登入 → 401 Unauthorized |
| `DELETE /api/meetings/{id}` | 未登入 → 401 Unauthorized |
| 其他所有 `/api/*` 端點 | 未登入 → 401 Unauthorized |

> **頁面 vs API 的差別**：
> - 頁面路由（沒有 `/api` 前綴）：未登入時「重新導向」到登入頁（因為是瀏覽器在看）
> - API 路由（有 `/api` 前綴）：未登入時回傳 401 錯誤碼（因為是 JavaScript/HTMX 在呼叫）

---

## 認證流程圖

```
使用者打開瀏覽器
    │
    ▼
訪問任何頁面（例如 /meetings）
    │
    ▼
伺服器檢查：有 session cookie 嗎？
    │
    ├── 沒有 → 302 重導到 /login?next=/meetings
    │           │
    │           ▼
    │       顯示登入頁面
    │           │
    │           ▼
    │       使用者輸入帳號密碼 → POST /login
    │           │
    │           ├── 驗證失敗 → 重新顯示登入頁（帶錯誤訊息）
    │           │
    │           └── 驗證成功 → 建立 session → 302 重導到 /meetings
    │
    └── 有 → 檢查 session 是否過期？
              │
              ├── 過期 → 302 重導到 /login?expired=1
              │
              └── 有效 → 正常顯示頁面，把使用者資訊傳給模板
```
