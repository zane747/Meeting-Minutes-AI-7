# Tasks: 帳號管理

**Feature Branch**: `007-account-management`
**Generated**: 2026-03-30
**Total Tasks**: 14
**Source**: spec.md, plan.md, data-model.md, contracts/api-endpoints.md, research.md

---

## Phase 1: Foundational（基礎建設）

> 擴充服務層和依賴層，為所有 User Story 提供共用基礎。

- [x] T001 在 `app/services/auth_service.py` 新增 `get_all_users(db)` 函式，回傳所有使用者列表（依 created_at 倒序）
- [x] T002 [P] 在 `app/services/auth_service.py` 新增 `get_active_user_count(db)` 函式，回傳目前啟用帳號數量
- [x] T003 在 `app/services/auth_service.py` 新增 `change_password(db, user_id, old_password, new_password)` 函式，驗證舊密碼後更新密碼雜湊值
- [x] T004 在 `app/services/auth_service.py` 新增 `toggle_user_active(db, user_id, operator_id)` 函式，切換帳號啟用/停用狀態，包含「不能操作自己」和「至少一個啟用帳號」保護
- [x] T005 [P] 在 `app/services/auth_service.py` 新增 `delete_user(db, user_id, operator_id)` 函式，刪除帳號，包含「不能刪除自己」和「至少一個帳號」保護
- [x] T006 修改 `app/dependencies.py` 的 `get_current_user()` 函式，新增從資料庫查詢 `is_active` 狀態的檢查，被停用的帳號清除 session 並導向登入頁

**Phase 1 驗收**：所有新函式可獨立呼叫測試，get_current_user 能擋住被停用的帳號

---

## Phase 2: User Story 1 — 檢視帳號列表 (P1)

> **目標**：使用者可以查看所有帳號的列表。
> **獨立測試**：登入後訪問 /accounts，確認能看到所有帳號。

- [x] T007 [US1] 新增 `app/templates/accounts.html`（繼承 base.html，顯示帳號列表表格：帳號名稱、狀態標籤、建立時間、操作按鈕），樣式使用 Tailwind CSS
- [x] T008 [US1] 新增 `app/api/routes/accounts.py`，實作 `GET /accounts`（查詢所有使用者 → 渲染 accounts.html），並在 `app/main.py` 註冊 accounts router
- [x] T009 [US1] 修改 `app/templates/base.html`，在導覽列新增「帳號管理」連結指向 `/accounts`

**Phase 2 驗收**：登入後能看到帳號列表頁面，顯示所有帳號的名稱、狀態、建立時間

---

## Phase 3: User Story 2 — 修改自己的密碼 (P1)

> **目標**：使用者可以修改自己的密碼。
> **獨立測試**：輸入舊密碼和新密碼，修改成功後用新密碼登入。

- [x] T010 [US2] 新增 `app/templates/change_password.html`（繼承 base.html，包含舊密碼、新密碼欄位、成功/錯誤訊息顯示），樣式使用 Tailwind CSS
- [x] T011 [US2] 在 `app/api/routes/accounts.py` 實作 `GET /accounts/change-password`（渲染修改密碼頁）和 `POST /accounts/change-password`（驗證舊密碼 → 更新新密碼 → 顯示成功訊息）
- [x] T012 [US2] 修改 `app/templates/base.html`，在導覽列使用者名稱旁新增「修改密碼」連結指向 `/accounts/change-password`

**Phase 3 驗收**：能修改密碼，舊密碼錯誤有提示，修改成功後用新密碼能登入

---

## Phase 4: User Story 3+4 — 停用/啟用 (P2) + 刪除帳號 (P3)

> **目標**：在帳號列表頁面操作停用/啟用/刪除。
> **獨立測試**：停用後該帳號無法登入；刪除後帳號消失。

- [x] T013 [US3] 在 `app/api/routes/accounts.py` 實作 `POST /api/accounts/{user_id}/toggle-active`（停用/啟用切換，回傳 JSON）和 `DELETE /api/accounts/{user_id}`（刪除帳號，回傳 JSON），在 `app/templates/accounts.html` 加入停用/啟用按鈕、刪除按鈕（含 JavaScript 二次確認 confirm 對話框）和 AJAX 呼叫邏輯

**Phase 4 驗收**：停用帳號後無法登入；啟用後恢復；刪除有二次確認且帳號消失；不能操作自己；最後一個帳號不能停用/刪除

---

## Phase 5: Polish（測試）

- [x] T014 新增 `tests/test_accounts.py`，測試案例包含：帳號列表顯示、修改密碼成功、舊密碼錯誤、停用帳號後無法登入、啟用帳號恢復、不能停用/刪除自己、最後帳號保護、刪除帳號成功

**Phase 5 驗收**：所有測試通過

---

## Dependencies（任務依賴）

```
Phase 1 (Foundational)
  T001, T002 → T008（列表需要 get_all_users）
  T003 → T011（修改密碼需要 change_password）
  T004, T005 → T013（停用/刪除需要 toggle/delete 函式）
  T006 → 所有 Phase（get_current_user 修改影響全局）

Phase 2 (US1 帳號列表)
  T007, T008, T009 依序執行

Phase 3 (US2 修改密碼)
  T010, T011, T012 依序執行（可與 Phase 2 並行）

Phase 4 (US3+4 停用/刪除)
  T013 依賴 Phase 2 完成（需要 accounts.html 和 accounts.py 已存在）

Phase 5 (測試)
  T014 依賴所有功能完成
```

---

## Implementation Strategy

### MVP Scope

**MVP = Phase 1 + 2 + 3**（T001 ~ T012）

完成後你就有：帳號列表 + 修改密碼。這兩個是 P1 優先級，可以先 demo。

### 你會學到的新概念

| Phase | 新概念 |
|-------|--------|
| Phase 1 | CRUD 的 Read/Update/Delete 在服務層怎麼寫 |
| Phase 2 | 列表頁面的模板渲染（for 迴圈、狀態標籤） |
| Phase 3 | 表單的進階用法（舊密碼 + 新密碼，成功/失敗訊息） |
| Phase 4 | 前端 JavaScript 呼叫 API（fetch + confirm 二次確認） |
| Phase 5 | 更複雜的測試案例（多使用者互動場景） |
