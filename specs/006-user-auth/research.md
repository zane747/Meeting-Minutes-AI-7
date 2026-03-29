# Research: 使用者登入登出系統

> 本文件記錄技術決策、選型理由與替代方案評估。
> 【新手導讀】每個決策都會解釋「為什麼這樣選」，幫助你理解背後的思考邏輯。

---

## 決策 1：密碼雜湊（Hashing）方案

### 什麼是密碼雜湊？

> **術語解釋**：雜湊（Hash）是一種「單向」的加密方式。
> 就像把一張紙丟進碎紙機——你可以把紙變成碎片，但無法把碎片還原成紙。
> 所以即使有人偷了資料庫，也看不到使用者的原始密碼。

**Decision（決策）**: 使用 `passlib` 套件搭配 `bcrypt` 演算法

**Rationale（理由）**:
- `bcrypt` 是業界公認最安全的密碼雜湊演算法之一
- `passlib` 是 Python 中最成熟的密碼處理套件，FastAPI 官方文件也推薦使用
- 支援「鹽值」（salt）——即使兩個使用者用同樣的密碼，雜湊出來的結果也不同
- 自動處理雜湊的「工作因子」（work factor），讓暴力破解變得很慢

**Alternatives considered（替代方案）**:
| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| `hashlib` (Python 內建) | 不需安裝套件 | 不支援 salt，不是為密碼設計的，不安全 | ❌ 不適合 |
| `argon2-cffi` | 更新的演算法，理論上更安全 | 需要額外的 C 編譯環境，在 Windows 上可能有安裝問題 | 可行但複雜度高 |
| `passlib[bcrypt]` | 成熟穩定、FastAPI 官方推薦、跨平台 | 需安裝套件 | ✅ 選用 |

---

## 決策 2：Session 管理方案

### 什麼是 Session？

> **術語解釋**：Session（會話）就像是餐廳給你的號碼牌。
> 你第一次登入（點餐）時，伺服器給你一個「號碼牌」（session ID），
> 之後每次操作，瀏覽器都會自動把號碼牌帶上，伺服器看到號碼牌就知道「喔，是你」。
> 這個號碼牌存在瀏覽器的 Cookie 裡。

**Decision（決策）**: 使用 `starlette-session` 搭配 server-side session 存儲

**Rationale（理由）**:
- FastAPI 是建立在 Starlette 之上的（就像 Starlette 是地基，FastAPI 是蓋在上面的房子）
- `starlette-session` 原生支援 server-side session，session 資料存在伺服器端，Cookie 只存 session ID
- 比 JWT（JSON Web Token）更適合 Jinja2 模板的伺服器端渲染架構
- session 資料不會暴露給瀏覽器，更安全

**Alternatives considered（替代方案）**:
| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| JWT (JSON Web Token) | 無狀態，不需要伺服器端存儲 | 對 Jinja2 模板不友善，登出困難（token 已發出無法撤銷） | 不適合本架構 |
| `itsdangerous` 簽名 Cookie | 輕量，不需要額外套件 | session 資料存在 Cookie 中（大小有限、資料暴露風險） | 可行但不理想 |
| `starlette-session` | 原生支援、server-side、安全 | 需安裝套件 | ✅ 選用 |

---

## 決策 3：認證中間件（Middleware）vs 依賴注入（Dependency）

### 什麼是中間件和依賴注入？

> **術語解釋**：
> - **中間件（Middleware）** 像大樓的門禁保全——每個人進大樓都要刷卡，不管你要去幾樓。
> - **依賴注入（Dependency Injection）** 像每個辦公室門口的門禁——只有需要的房間才裝鎖。
>
> 中間件是「全域」的（所有請求都經過），依賴注入是「按需」的（只有標記的路由才檢查）。

**Decision（決策）**: 使用 FastAPI 的 `Depends()` 依賴注入作為主要認證機制

**Rationale（理由）**:
- 專案已經有使用 `Depends()` 的慣例（`get_audio_processor`、`get_db`）
- 可以精確控制哪些路由需要認證、哪些不需要（如登入頁、註冊頁）
- 方便在路由函式中直接取得當前使用者的資訊
- 比全域中間件更靈活——登入頁和註冊頁不需要認證

**How it works（怎麼運作）**:
```
使用者發出請求 → FastAPI 收到請求
    → 看到路由有 Depends(get_current_user)
    → 先執行 get_current_user：從 Cookie 讀取 session ID → 查詢是否有效
    → 有效：把使用者資訊傳給路由函式，繼續處理
    → 無效：直接回傳 401 或導向登入頁，路由函式根本不會被執行
```

**Alternatives considered（替代方案）**:
| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| 全域 Middleware | 所有路由自動保護 | 需要維護「白名單」，與現有架構風格不一致 | 不適合 |
| `Depends()` 依賴注入 | 精確控制、與現有架構一致、可取得使用者 | 需要在每個路由加上 Depends | ✅ 選用 |

---

## 決策 4：新增依賴套件

**Decision（決策）**: 新增以下套件至 `pyproject.toml`

| 套件 | 用途 | 為什麼需要它 |
|------|------|-------------|
| `passlib[bcrypt]` | 密碼雜湊 | 安全地儲存和驗證密碼 |
| `starlette-session` | Session 管理 | 維持登入狀態（server-side session） |

**不需要額外安裝的**（已有）:
- `fastapi` — 已有
- `sqlalchemy` — 已有，User model 直接加入
- `jinja2` — 已有，登入/註冊頁面用

---

## 決策 5：Session 過期提示的實作策略

**Decision（決策）**: 使用 URL query parameter 傳遞過期訊息

**How it works（怎麼運作）**:
```
Session 過期 → 伺服器偵測到無效 session
    → 導向 /login?expired=1
    → 登入頁面的 Jinja2 模板檢查 expired 參數
    → 如果有，顯示「登入已過期，請重新登入」提示
```

**Rationale（理由）**:
- 簡單直覺，不需要額外的前端框架或 JavaScript
- 符合現有 Jinja2 模板架構
- 使用者重新整理頁面後提示自然消失（不會一直卡在那裡）
