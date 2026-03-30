# Implementation Plan: 權限管理

**Feature Branch**: `008-role-permission`
**Created**: 2026-03-30
**Status**: Ready for Tasks

---

## Technical Context

沿用現有技術棧，不需要新增套件。

---

## Constitution Check

| 守則 | 狀態 |
|------|------|
| 模組化設計 / SRP | ✅ 權限檢查獨立為 require_role 依賴函式 |
| Docstring 規範 | ✅ |
| 型別註解 | ✅ |
| 命名慣例 | ✅ |
| 測試標準 | ✅ 新增 test_permissions.py |
| 錯誤處理 | ✅ 403 Forbidden |
| 安全性 | ✅ 後端強制檢查角色 |

---

## Architecture Overview

### 新增/修改的檔案

```
app/
├── models/
│   └── database_models.py     ← 【修改】User 新增 role、Meeting 新增 created_by + visibility
├── dependencies.py            ← 【修改】get_current_user 回傳 role、新增 require_role()
├── services/
│   └── auth_service.py        ← 【修改】create_user 自動設角色、新增 change_role()、get_admin_count()
├── api/routes/
│   ├── auth.py                ← 【修改】註冊時自動設角色
│   ├── accounts.py            ← 【修改】加角色權限檢查、角色變更 API、過濾帳號列表
│   ├── meetings.py            ← 【修改】上傳加 created_by + visibility、列表加可見性過濾
│   ├── pages.py               ← 【修改】會議列表加可見性過濾
│   └── admin.py               ← 【新增】管理中心路由（等級 1 專屬）
├── templates/
│   ├── base.html              ← 【修改】導覽列根據角色顯示不同連結
│   ├── admin_dashboard.html   ← 【新增】管理中心頁面
│   ├── accounts.html          ← 【修改】加角色顯示和變更按鈕
│   └── index.html             ← 【修改】上傳表單加可見性選擇
tests/
└── test_permissions.py        ← 【新增】權限功能測試
```

### 資料流

```
【權限檢查流程】
請求進來 → get_current_user（從 DB 讀 role）
    → require_role(N) 檢查 role <= N
    → 通過 → 路由執行
    → 不通過 → 403

【會議列表過濾】
GET /meetings → 根據 current_user.role 組裝 SQL WHERE 條件
    → 等級 1：不過濾
    → 等級 2：自己的 + 公開的 + 等級 3 的 + 同級同等級可見的
    → 等級 3：自己的 + 公開的 + 同級同等級可見的

【角色變更】
POST /api/accounts/{id}/change-role → require_role(1) → auth_service.change_role()
    → 檢查目標不是等級 1 → 檢查不是自己 → 更新 role → 回傳成功
```

---

## Implementation Phases

### Phase 1: 資料模型變更

- User 表新增 `role` 欄位（Integer, 預設 3）
- Meeting 表新增 `created_by`（FK → User.id, nullable）和 `visibility`（String, 預設 "private"）

### Phase 2: 依賴層

- `get_current_user` 回傳新增 `role` 欄位
- 新增 `require_role(max_level)` 依賴函式工廠

### Phase 3: 服務層

- `create_user` 判斷是否第一個帳號，自動設 role
- 新增 `change_role()`、`get_admin_count()`
- 修改帳號管理函式加入角色檢查

### Phase 4: 路由 + 頁面

- 新增 admin.py（管理中心）
- 修改 accounts.py（角色過濾 + 變更 API）
- 修改 meetings.py（上傳加 created_by/visibility、列表加過濾）
- 修改 pages.py（會議列表過濾）
- 修改所有模板（導覽列、帳號列表、上傳表單）
- 新增 admin_dashboard.html

### Phase 5: 登入提示優化 + 測試

- 修改 auth_service.authenticate_user 區分停用帳號
- 新增 test_permissions.py

---

## Risk Assessment

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| 會議列表的過濾查詢複雜 | 中 | 先寫出正確的 SQL 查詢，再優化 |
| 既有會議紀錄 created_by 為 null | 低 | 明確定義為公開，查詢時特別處理 |
| 角色變更的即時生效 | 低 | get_current_user 已經每次都查 DB |
| 等級 2 帳號管理的過濾邏輯 | 中 | 共用 /accounts 頁面，後端根據角色過濾 |
