# Tasks: 使用者登入登出系統

**Feature Branch**: `006-user-auth`
**Generated**: 2026-03-27
**Total Tasks**: 19
**Source**: spec.md, plan.md, data-model.md, contracts/api-endpoints.md, research.md

---

## Phase 1: Setup（環境準備）

> 安裝套件、設定環境變數。這些是所有後續工作的前提。

- [x] T001 新增 `passlib[bcrypt]` 和 `starlette-session` 依賴至 `pyproject.toml` 並執行 `uv sync` 安裝
- [x] T002 [P] 在 `app/config.py` 新增 `SESSION_SECRET_KEY: str` 設定欄位
- [x] T003 [P] 在 `.env` 和 `.env.example` 新增 `SESSION_SECRET_KEY` 環境變數

**Phase 1 驗收**：`uv sync` 成功、應用程式可正常啟動、config 可讀取 SESSION_SECRET_KEY

---

## Phase 2: Foundational（基礎建設）

> 建立 User 資料模型和認證服務。這些是所有使用者故事共用的基礎元件。

- [x] T004 在 `app/models/database_models.py` 新增 User 模型（id, username, password_hash, is_active, created_at, updated_at），包含 UNIQUE 索引
- [x] T005 [P] 在 `app/models/schemas.py` 新增 `UserCreate`（username 正則驗證 + password 長度驗證）和 `UserLogin` Pydantic schemas
- [x] T006 新增 `app/services/auth_service.py`，實作 `hash_password()`、`verify_password()`、`create_user()`、`authenticate_user()` 四個函式
- [x] T007 在 `app/main.py` 加入 `SessionMiddleware`（使用 config 中的 SESSION_SECRET_KEY，設定 max_age=86400、httponly=True、samesite=lax）
- [x] T008 在 `app/dependencies.py` 新增 `get_current_user()` 依賴函式（從 session 讀取 user_id，無效則頁面路由導向 /login、API 路由回傳 401）
- [x] T009 [P] 在 `app/dependencies.py` 新增 `get_current_user_optional()` 依賴函式（同上但允許未登入，回傳 None）

**Phase 2 驗收**：應用程式啟動後自動建立 `users` 表、auth_service 的密碼雜湊和驗證可正常運作

---

## Phase 3: User Story 1 — 使用者註冊帳號 (P1)

> **目標**：使用者可以填寫帳號密碼完成註冊，自動登入並導向首頁。
> **獨立測試**：開啟 /register → 填表 → 確認跳轉首頁且帳號已建立。

- [x] T010 [US1] 新增 `app/templates/register.html`（繼承 base.html，包含帳號密碼表單、錯誤訊息顯示、「前往登入」連結），樣式使用 Tailwind CSS
- [x] T011 [US1] 在 `app/api/routes/auth.py` 實作 `GET /register`（渲染註冊頁）和 `POST /register`（表單驗證 → 建立帳號 → 建立 session → 302 導向首頁），並在 `app/main.py` 註冊 auth router

**Phase 3 驗收**：可完成註冊流程；重複帳號顯示錯誤；格式不符顯示驗證錯誤

---

## Phase 4: User Story 2 — 使用者登入 (P1)

> **目標**：已註冊使用者可輸入帳密登入，成功後導向首頁並顯示使用者名稱。
> **獨立測試**：開啟 /login → 輸入正確/錯誤帳密 → 確認登入結果。

- [x] T012 [US2] 新增 `app/templates/login.html`（繼承 base.html，包含帳號密碼表單、錯誤訊息、expired 參數提示「登入已過期，請重新登入」、next 隱藏欄位、「前往註冊」連結），樣式使用 Tailwind CSS
- [x] T013 [US2] 在 `app/api/routes/auth.py` 實作 `GET /login`（渲染登入頁，支援 next 和 expired query params）和 `POST /login`（驗證帳密 → 建立 session → 302 導向 next 或首頁）

**Phase 4 驗收**：登入成功跳轉首頁；錯誤密碼顯示統一錯誤訊息；session 過期顯示提示

---

## Phase 5: User Story 3 — 使用者登出 (P1)

> **目標**：已登入使用者可登出，清除 session 並導向登入頁。
> **獨立測試**：登入後點登出 → 確認回到登入頁 → 再訪問首頁被攔截。

- [x] T014 [US3] 在 `app/api/routes/auth.py` 實作 `POST /logout`（需認證，清除 session → 302 導向 /login）
- [x] T015 [US3] 修改 `app/templates/base.html`，在導覽列右側加入：已登入時顯示使用者名稱和登出按鈕（POST 表單），未登入時顯示登入連結

**Phase 5 驗收**：登出後 session 被清除；導覽列正確顯示使用者狀態

---

## Phase 6: User Story 4 — 未登入使用者被導向登入頁 (P2)

> **目標**：所有受保護的頁面和 API 都必須通過認證檢查。
> **獨立測試**：未登入直接訪問 /meetings → 被導向 /login；登入後導回原頁面。

- [x] T016 [US4] 修改 `app/api/routes/pages.py`，所有頁面路由加上 `Depends(get_current_user)` 認證檢查，未登入時 302 導向 `/login?next=原路徑`
- [x] T017 [US4] 修改 `app/api/routes/meetings.py`，所有 API 路由加上 `Depends(get_current_user)` 認證檢查，未登入時回傳 401 Unauthorized
- [x] T018 [US4] 修改 `app/api/routes/pages.py` 中的模板渲染，將 current_user 資訊傳入所有 Jinja2 模板（讓 base.html 的導覽列可以讀取使用者名稱）

**Phase 6 驗收**：未登入訪問任何頁面 → 導向登入頁；未登入呼叫 API → 401；登入後 next 導回正確

---

## Phase 7: Polish（收尾與測試）

- [x] T019 新增 `tests/test_auth.py`，測試案例包含：註冊成功、重複帳號失敗、登入成功、錯誤密碼失敗、登出成功、未登入訪問受保護頁面被導向、未登入呼叫 API 收到 401

**Phase 7 驗收**：所有測試通過

---

## Dependencies（任務依賴關係）

```
Phase 1 (Setup)
  T001 ──→ T004, T006, T007（套件安裝後才能使用 passlib/starlette-session）
  T002, T003 ──→ T007（config 設定後才能設定 middleware）

Phase 2 (Foundational)
  T004 ──→ T006（User model 建好後才能寫 auth_service）
  T005 可與 T004 並行（Pydantic schema 不依賴 ORM model）
  T006 ──→ T011, T013（auth_service 建好後才能在路由中使用）
  T007 ──→ T008, T009（middleware 設好後才能讀 session）
  T008 ──→ T014, T016, T017（認證依賴函式建好後路由才能使用）

Phase 3-5 (User Stories 1-3) — 建議按順序做，但技術上可並行
  T011 (註冊路由) ──→ T013 (登入路由)（要先有帳號才能測試登入）
  T013 ──→ T014 (登出路由)（要先能登入才能測試登出）

Phase 6 (User Story 4) — 依賴 Phase 3-5 完成
  T016, T017, T018 依賴 T008（認證依賴函式）

Phase 7 (Polish) — 依賴所有功能完成
  T019 依賴 T001-T018 全部完成
```

---

## Parallel Opportunities（可並行的任務）

| 階段 | 可並行的任務 | 說明 |
|------|-------------|------|
| Phase 1 | T002 + T003 | config 和 .env 互不影響 |
| Phase 2 | T004 + T005 | ORM model 和 Pydantic schema 互不影響 |
| Phase 2 | T008 + T009 | 兩個依賴函式互不影響 |
| Phase 6 | T016 + T017 + T018 | 三個路由檔案各自獨立修改 |

---

## Implementation Strategy（實作策略）

### MVP Scope（最小可行版本）

**建議 MVP = Phase 1 + 2 + 3 + 4 + 5**（T001 ~ T015）

完成後你就有一個可以：
1. 註冊帳號
2. 登入系統
3. 看到自己的名字
4. 登出系統

的完整流程。即使 Phase 6（保護現有路由）還沒做，你已經可以 demo 給主管看了。

### 建議的學習順序

每做完一個 Phase，停下來回答自己這些問題：

| Phase | 問自己 |
|-------|--------|
| Phase 1 | 「pyproject.toml 是什麼？為什麼不直接用 pip install？」 |
| Phase 2 | 「密碼為什麼要雜湊？如果直接存明文會怎樣？」 |
| Phase 3 | 「表單的資料是怎麼從 HTML 傳到 Python 的？」 |
| Phase 4 | 「Session 是怎麼讓伺服器『記住』我已經登入的？」 |
| Phase 5 | 「登出時伺服器做了什麼？Cookie 發生了什麼變化？」 |
| Phase 6 | 「Depends() 在每次請求時被執行了幾次？執行順序是什麼？」 |
| Phase 7 | 「測試為什麼重要？如果不寫測試，風險是什麼？」 |
