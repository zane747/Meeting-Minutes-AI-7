# Tasks: 權限管理

**Feature Branch**: `008-role-permission`
**Generated**: 2026-03-30
**Total Tasks**: 21
**Source**: spec.md, plan.md, data-model.md, contracts/api-endpoints.md, research.md

---

## Phase 1: 資料模型變更

> User 新增 role 欄位、Meeting 新增 created_by + visibility 欄位。

- [x] T001 修改 `app/models/database_models.py`，在 User 模型新增 `role` 欄位（Integer, NOT NULL, 預設 3），值 1=超級管理員 2=管理員 3=一般使用者
- [x] T002 [P] 修改 `app/models/database_models.py`，在 Meeting 模型新增 `created_by` 欄位（String(36), FK → users.id, nullable）和 `visibility` 欄位（String(20), NOT NULL, 預設 "public"，可選值 public/private/same_level）

**Phase 1 驗收**：應用程式啟動後資料庫自動新增欄位，既有資料不受影響

---

## Phase 2: Foundational（依賴層 + 服務層基礎）

> 權限檢查機制、角色自動設定、角色變更函式。

- [x] T003 修改 `app/dependencies.py` 的 `get_current_user()`，回傳的 dict 新增 `role` 欄位（從資料庫讀取 User.role）
- [x] T004 在 `app/dependencies.py` 新增 `require_role(max_level: int)` 依賴函式工廠，檢查 current_user["role"] <= max_level，不通過則頁面路由導向首頁、API 路由回傳 403
- [x] T005 修改 `app/services/auth_service.py` 的 `create_user()` 函式，註冊時判斷若資料庫中無任何帳號則設 role=1（超級管理員），否則設 role=3（一般使用者）
- [x] T006 在 `app/services/auth_service.py` 新增 `change_role(db, user_id, new_role, operator_id)` 函式，包含保護規則：只能操作等級 2 和 3、不能操作自己、至少保留一個等級 1
- [x] T007 [P] 在 `app/services/auth_service.py` 新增 `get_admin_count(db)` 函式，回傳等級 1 帳號數量

**Phase 2 驗收**：第一個註冊帳號自動為等級 1，後續為等級 3；require_role 能正確擋住權限不足的請求

---

## Phase 3: User Story 1+2 — 角色分級 + 管理員專屬功能 (P1)

> 帳號列表顯示角色、等級 2 只看等級 3、等級 3 看不到帳號管理。

- [x] T008 [US1] 修改 `app/api/routes/accounts.py` 的帳號列表路由，加入 `require_role(2)` 權限檢查，並根據角色過濾帳號列表（等級 1 看全部、等級 2 只看等級 3）
- [x] T009 [US1] 修改 `app/templates/accounts.html`，帳號列表新增「角色」欄位顯示（等級 1/2/3 標籤），等級 1 帳號行顯示角色變更按鈕
- [x] T010 [US2] 修改 `app/api/routes/accounts.py` 的停用/啟用/刪除 API，新增角色檢查：等級 2 只能操作等級 3 的帳號、等級 3 直接 403
- [x] T011 [US2] 修改 `app/templates/base.html`，導覽列根據 current_user.role 顯示不同連結（等級 1：管理中心+帳號管理、等級 2：帳號管理、等級 3：只有基本功能）

**Phase 3 驗收**：等級 3 無法訪問 /accounts（403）；等級 2 只看到等級 3 帳號；等級 1 看到全部

---

## Phase 4: User Story 2 續 — 管理中心 + 角色變更 (P1/P2)

> 等級 1 的獨立管理介面、角色變更功能。

- [x] T012 [US2] 新增 `app/templates/admin_dashboard.html`（繼承 base.html，顯示所有會議紀錄列表含上傳者名稱、連結到帳號管理），樣式使用 Tailwind CSS
- [x] T013 [US2] 新增 `app/api/routes/admin.py`，實作 `GET /admin`（require_role(1)，查詢所有會議含上傳者 → 渲染 admin_dashboard.html），並在 `app/main.py` 註冊 admin router
- [x] T014 [US3] 在 `app/api/routes/accounts.py` 新增 `POST /api/accounts/{user_id}/change-role` API（require_role(1)，接收 JSON body {role: 2 或 3}，呼叫 auth_service.change_role()）
- [x] T015 [US3] 修改 `app/templates/accounts.html`，等級 1 帳號行顯示角色變更下拉選單或按鈕（升為等級 2 / 降為等級 3），用 JavaScript fetch 呼叫 change-role API

**Phase 4 驗收**：等級 1 能訪問管理中心看到所有會議；能變更等級 2/3 帳號的角色

---

## Phase 5: User Story 3+4 — 會議可見性 + 列表過濾 (P2)

> 上傳時選擇可見性、列表根據角色和可見性過濾。

- [x] T016 [US3] 修改 `app/api/routes/meetings.py` 的 `upload_and_process` 函式，新增 `visibility` 表單參數（預設 "private"）和 `created_by` 自動填入 current_user["user_id"]
- [x] T017 [US3] 修改 `app/templates/index.html`，上傳表單新增「可見性」下拉選單（公開/僅自己/同等級可見）
- [x] T018 [US4] 修改 `app/api/routes/pages.py` 的會議列表路由，根據 current_user.role 和 visibility 欄位過濾會議紀錄（等級 1 不過濾、等級 2 看自己+公開+等級 3 的+同級同等級可見、等級 3 看自己+公開+同級同等級可見，created_by 為 null 視為公開）
- [x] T019 [US4] 新增 `PUT /api/meetings/{meeting_id}/visibility` API 在 `app/api/routes/meetings.py`（上傳者本人或等級 1 可修改），接收 JSON body {visibility: "public"/"private"/"same_level"}

**Phase 5 驗收**：上傳時可選可見性；等級 3 只看到自己的+公開的；等級 2 額外看到等級 3 的；等級 1 看全部

---

## Phase 6: User Story 5 — 停用帳號提示 + 測試 (P3)

> 修復被停用帳號的登入提示、完整測試。

- [x] T020 [US5] 修改 `app/services/auth_service.py` 的 `authenticate_user()` 函式，區分「帳號被停用」和「帳號密碼錯誤」的回傳，修改 `app/api/routes/auth.py` 的登入路由，被停用帳號顯示「帳號已被停用，請聯繫管理員」
- [x] T021 新增 `tests/test_permissions.py`，測試案例包含：第一個帳號自動等級 1、後續帳號等級 3、等級 3 無法訪問帳號管理、角色變更、停用帳號登入提示

**Phase 6 驗收**：所有測試通過

---

## Dependencies

```
Phase 1 (資料模型)
  T001, T002 → 所有後續 Phase（欄位要先建好）

Phase 2 (依賴層+服務層)
  T003, T004 → T008, T010, T013（權限檢查機制）
  T005 → T021（自動角色測試）
  T006, T007 → T014（角色變更）

Phase 3 (角色分級+管理員功能)
  T008~T011 依序執行

Phase 4 (管理中心+角色變更)
  T012, T013 依序（管理中心頁面+路由）
  T014, T015 依序（角色變更 API + 前端）

Phase 5 (會議可見性)
  T016, T017 依序（上傳修改）
  T018 依賴 T016（有 visibility 欄位才能過濾）
  T019 可與 T018 並行

Phase 6 (提示+測試)
  T020, T021 依賴所有前面完成
```

---

## Implementation Strategy

### MVP Scope

**MVP = Phase 1 + 2 + 3**（T001 ~ T011）

完成後有：三級角色 + 帳號管理權限控制 + 導覽列根據角色顯示。

### 你會學到的新概念

| Phase | 新概念 |
|-------|--------|
| Phase 1 | 資料庫 Migration 的概念（新增欄位到現有表） |
| Phase 2 | 依賴函式工廠（函式回傳函式）— require_role(N) |
| Phase 3 | 根據角色動態過濾資料（同一個頁面，不同人看到不同內容） |
| Phase 4 | 獨立的管理介面（角色專屬頁面） |
| Phase 5 | 複雜的 SQL 查詢條件組裝（多欄位過濾） |
| Phase 6 | 區分不同的錯誤類型回傳不同訊息 |
