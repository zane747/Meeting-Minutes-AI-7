# 學習筆記：登入登出功能

> 這份筆記記錄了做「使用者登入登出」功能時學到的所有概念。
> 日後忘記時可以回來翻，每個概念都有「白話解釋 + 對應的程式碼位置」。

**完成日期**: 2026-03-28
**功能分支**: `006-user-auth`

---

## 一、我學到的核心概念

### 1. HTTP 請求方法（GET vs POST）

**白話解釋**：
- **GET** = 「給我東西」— 瀏覽器跟伺服器說「我要看這個頁面」
- **POST** = 「幫我處理」— 瀏覽器跟伺服器說「這是我填的資料，幫我存起來」

**為什麼登出要用 POST 不用 GET？**
如果登出用 GET，別人可以在網頁裡偷放 `<img src="/logout">`，你一打開那個頁面就被強制登出了。這叫 **CSRF 攻擊**。

**在程式碼裡哪裡看得到**：
- `app/api/routes/auth.py` — `@router.get("/login")` 是顯示頁面，`@router.post("/login")` 是處理表單

---

### 2. 密碼雜湊（Hash）

**白話解釋**：
雜湊就像碎紙機 — 你可以把一張紙變成碎片，但不能把碎片還原成紙。

```
使用者輸入: "mypassword123"
        ↓ bcrypt 雜湊
資料庫存的: "$2b$12$LJ3m4ks9fj2k..." (一串亂碼)
```

**為什麼要這樣做？**
如果資料庫被駭客偷了，他們看到的只是亂碼，不知道原始密碼。

**登入時怎麼驗證？**
把使用者輸入的密碼再做一次雜湊，跟資料庫裡的比較。一樣就是密碼正確。

**在程式碼裡哪裡看得到**：
- `app/services/auth_service.py` — `hash_password()` 和 `verify_password()`

---

### 3. Session 和 Cookie

**白話解釋**：
Session 就像餐廳的號碼牌機制：

```
你（瀏覽器）          餐廳（伺服器）
    │                    │
    │  "我要登入"         │
    │ ──────────────────→ │
    │                    │  驗證帳密 ✓
    │  "給你號碼牌 #42"   │  記下：#42 = 這個人
    │ ←────────────────── │
    │                    │
    │  "我要看會議紀錄"    │
    │  (自動帶著 #42)     │
    │ ──────────────────→ │
    │                    │  看到 #42，認出你了
    │  "好的，這是你的資料" │
    │ ←────────────────── │
```

- **Cookie**：瀏覽器端的號碼牌（存在你的電腦裡，每次請求自動帶上）
- **Session**：伺服器端的名單（記錄 #42 號是誰、什麼時候登入的）

**在程式碼裡哪裡看得到**：
- `app/main.py` — `SessionMiddleware` 設定（號碼牌機制的啟動）
- `app/api/routes/auth.py` — `request.session["user_id"] = user.id`（發號碼牌）
- `app/api/routes/auth.py` — `request.session.clear()`（收回號碼牌 = 登出）

---

### 4. 依賴注入（Dependency Injection）

**白話解釋**：
就像辦公室門口的門禁卡機。你不用自己帶保全，門禁系統會自動幫你檢查。

```python
# 這行的意思是：「這個路由需要登入才能用」
@router.get("/meetings")
async def history(current_user: dict = Depends(get_current_user)):
    ...
```

FastAPI 看到 `Depends(get_current_user)` 會做的事：
1. 先執行 `get_current_user` 函式
2. 如果有登入 → 把使用者資訊傳給 `history` 函式
3. 如果沒登入 → 直接擋掉，`history` 函式根本不會被執行

**在程式碼裡哪裡看得到**：
- `app/dependencies.py` — `get_current_user()` 的定義
- `app/api/routes/pages.py` — 每個路由都有 `Depends(get_current_user)`

---

### 5. ORM（物件關聯映射）

**白話解釋**：
讓你用 Python 的 class 操作資料庫，不需要寫 SQL。

```python
# 這不是 SQL，這是 Python！
# 但 SQLAlchemy 會自動翻譯成 SQL 去查資料庫
user = User(username="john", password_hash="...")
db.add(user)       # INSERT INTO users ...
await db.commit()  # 真正存入資料庫
```

**在程式碼裡哪裡看得到**：
- `app/models/database_models.py` — `User` class = 資料庫的 `users` 表
- `app/services/auth_service.py` — `create_user()` 裡用 `db.add()` 存資料

---

### 6. Jinja2 模板渲染

**白話解釋**：
伺服器端的「填空」系統。HTML 模板裡留空格，伺服器把資料填進去再送給瀏覽器。

```html
<!-- 模板（有空格） -->
{% if current_user %}
    <span>{{ current_user.username }}</span>
{% else %}
    <a href="/login">登入</a>
{% endif %}
```

伺服器會根據「這個人有沒有登入」來決定顯示什麼。瀏覽器收到的是已經填好的 HTML。

**注意事項**：
- Jinja2 的註解要用 `{# ... #}`，不能用 HTML 的 `<!-- -->`
- 因為 Jinja2 會解析 HTML 註解裡面的 `{{ }}` 和 `{% %}`

**在程式碼裡哪裡看得到**：
- `app/templates/base.html` — 導覽列根據登入狀態顯示不同內容
- `app/templates/login.html` — 錯誤訊息的條件顯示

---

### 7. 分層架構

**白話解釋**：
把程式碼按「職責」分開放，就像公司的部門分工：

```
模板層 (Templates)  ← 負責「畫面長什麼樣子」
    ↕
路由層 (Routes)     ← 負責「接收請求、回傳回應」
    ↕
服務層 (Services)   ← 負責「商業邏輯」（密碼雜湊、驗證等）
    ↕
資料層 (Models)     ← 負責「資料結構和資料庫」
```

**為什麼要分層？**
如果以後要把 bcrypt 換成 argon2，只要改 `auth_service.py`，路由和模板完全不用動。

**對應的檔案**：
- 模板層：`app/templates/*.html`
- 路由層：`app/api/routes/auth.py`
- 服務層：`app/services/auth_service.py`
- 資料層：`app/models/database_models.py`

---

## 二、資料傳遞的完整流程

### 登入流程（從按下按鈕到看到首頁）

```
1. 使用者在 login.html 填寫帳號密碼，按「登入」
   ↓
2. 瀏覽器發出 POST /login 請求
   （資料格式：username=john&password=mypass123）
   ↓
3. FastAPI 收到請求，找到 auth.py 的 login() 函式
   ↓
4. login() 呼叫 auth_service.authenticate_user(db, username, password)
   ↓
5. authenticate_user() 去資料庫查 username → 找到 User 物件
   ↓
6. 用 bcrypt.checkpw() 比對密碼雜湊值
   ↓
7. 比對成功！在 session 中存入 user_id 和 username
   （request.session["user_id"] = user.id）
   ↓
8. 回傳 302 Redirect → 瀏覽器跳到首頁 /
   （同時瀏覽器收到 Set-Cookie，之後每次請求都會自動帶上）
   ↓
9. 瀏覽器訪問 /，FastAPI 執行 Depends(get_current_user)
   ↓
10. get_current_user() 從 session 讀到 user_id → 確認已登入
    ↓
11. 首頁正常顯示，導覽列顯示使用者名稱和登出按鈕
```

### 認證檢查流程（每次請求都會發生）

```
瀏覽器請求任何受保護頁面
    ↓
SessionMiddleware 從 Cookie 讀取 session ID
    ↓
載入對應的 session 資料到 request.session
    ↓
FastAPI 看到路由有 Depends(get_current_user)
    ↓
get_current_user() 檢查 request.session 有沒有 user_id
    ↓
├── 有 → 回傳使用者資訊 → 路由函式正常執行
│
└── 沒有 → 檢查是頁面路由還是 API 路由
         ├── 頁面路由 → 302 導向 /login?next=原路徑
         └── API 路由 → 401 Unauthorized JSON 錯誤
```

---

## 三、安全概念

| 攻擊手法 | 白話解釋 | 我們的防護 |
|---------|---------|----------|
| **密碼外洩** | 資料庫被偷，密碼被看光 | bcrypt 雜湊，看到的只是亂碼 |
| **帳號枚舉** | 攻擊者測試哪些帳號存在 | 錯誤訊息統一「帳號或密碼錯誤」 |
| **CSRF** | 惡意網站偷偷幫你送請求 | 登出用 POST + SameSite Cookie |
| **XSS 偷 Cookie** | JavaScript 偷讀你的 Cookie | Cookie 設定 HttpOnly |
| **瀏覽器快取洩漏** | 登出後按上一頁看到舊頁面 | Cache-Control: no-store |

---

## 四、開發流程（SDD — 規格驅動開發）

這是主管要求的開發方式，每個功能都跑這個流程：

```
/speckit.specify   → 寫規格書（做什麼、為什麼做）
/speckit.clarify   → 釐清模糊的需求
/speckit.plan      → 技術規劃（怎麼做）
/speckit.tasks     → 拆成任務清單
/speckit.analyze   → 檢查文件之間有沒有矛盾
/speckit.implement → 按任務寫程式
/speckit.checklist → 檢查需求品質
```

**重點**：先想清楚再動手寫，不是邊寫邊想。

---

## 五、常用指令速查

```bash
# 啟動伺服器
uv run uvicorn app.main:app --reload

# 跑測試
uv run python -m pytest tests/test_auth.py -v

# 安裝套件
uv add <套件名稱>

# 看 git 狀態
git status

# 測試密碼雜湊（Python shell）
uv run python -c "from app.services.auth_service import hash_password, verify_password; h = hash_password('test'); print(verify_password('test', h))"
```

---

## 六、這個功能動到的所有檔案

### 新增的
| 檔案 | 職責 |
|------|------|
| `app/services/auth_service.py` | 密碼雜湊、使用者建立、登入驗證 |
| `app/api/routes/auth.py` | 註冊/登入/登出的 URL 端點 |
| `app/templates/login.html` | 登入頁面的 HTML |
| `app/templates/register.html` | 註冊頁面的 HTML |
| `tests/test_auth.py` | 自動化測試（16 個案例） |

### 修改的
| 檔案 | 改了什麼 |
|------|---------|
| `pyproject.toml` | 新增 bcrypt、starlette-session 套件 |
| `app/config.py` | 新增 SESSION_SECRET_KEY 設定 |
| `app/main.py` | 加 SessionMiddleware、註冊 auth 路由 |
| `app/dependencies.py` | 新增 get_current_user 認證依賴 |
| `app/models/database_models.py` | 新增 User 資料表 |
| `app/models/schemas.py` | 新增 UserCreate/UserLogin 驗證模型 |
| `app/api/routes/pages.py` | 所有頁面加認證 + Cache-Control |
| `app/api/routes/meetings.py` | 所有 API 加認證 |
| `app/templates/base.html` | 導覽列加使用者名稱/登出按鈕 |

---

## 七、自我檢測問題

能回答這些問題，表示你真的懂了：

1. 使用者按下「登入」後，資料經過哪些檔案？
2. 伺服器怎麼知道「這個人已經登入」？
3. 為什麼密碼要雜湊？不雜湊會怎樣？
4. `Depends(get_current_user)` 做了什麼事？
5. 為什麼登出要用 POST 不用 GET？
6. 如果 session 過期了，使用者會看到什麼？
7. `Cache-Control: no-store` 解決了什麼問題？
8. 為什麼錯誤訊息不告訴使用者「帳號不存在」？
