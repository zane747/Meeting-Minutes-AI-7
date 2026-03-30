# API Contracts: 權限管理

---

## 新增端點

### 1. 管理中心頁面（等級 1 專屬）

```
GET /admin
```

| 項目 | 說明 |
|------|------|
| 用途 | 等級 1 的獨立管理介面（所有會議 + 角色變更入口） |
| 認證 | ✅ 需要登入 + 等級 1 |
| 回應 | HTML 頁面（admin_dashboard.html） |
| 非等級 1 訪問 | 403 或導向首頁 |

---

### 2. 變更角色 API（等級 1 專屬）

```
POST /api/accounts/{user_id}/change-role
```

| 項目 | 說明 |
|------|------|
| 用途 | 修改帳號的角色等級 |
| 認證 | ✅ 需要登入 + 等級 1 |
| Content-Type | `application/json` |

**請求 body**:

| 欄位 | 型別 | 說明 |
|------|------|------|
| `role` | integer | 目標角色等級（2 或 3） |

**保護規則**:
- 只能操作等級 2 和 3 → 否則 403
- 不能操作自己 → 403
- 降級後至少保留一個等級 1 → 403

---

### 3. 修改會議可見性

```
PUT /api/meetings/{meeting_id}/visibility
```

| 項目 | 說明 |
|------|------|
| 用途 | 修改會議紀錄的可見性設定 |
| 認證 | ✅ 需要登入（上傳者本人 或 等級 1） |
| Content-Type | `application/json` |

**請求 body**:

| 欄位 | 型別 | 說明 |
|------|------|------|
| `visibility` | string | "public" / "private" / "same_level" |

---

## 修改的端點

### 帳號管理頁面（/accounts）

- 等級 1：看到所有帳號 + 角色變更按鈕
- 等級 2：只看到等級 3 的帳號（停用/啟用/刪除）
- 等級 3：403 禁止訪問

### 帳號操作 API（toggle-active、delete）

新增角色檢查：
- 等級 1：可操作所有等級 2、3 的帳號
- 等級 2：只能操作等級 3 的帳號
- 等級 3：403

### 會議列表（/meetings、/api/meetings）

根據角色和可見性過濾會議紀錄（詳見 data-model.md 查詢邏輯）。

### 會議上傳（/api/meetings/upload-and-process）

- 新增 `visibility` 表單欄位（預設 "private"）
- 自動填入 `created_by` = 當前使用者 ID

### 導覽列（base.html）

| 角色 | 顯示的連結 |
|------|-----------|
| 等級 1 | 上傳、歷史紀錄、管理中心、帳號管理、修改密碼、登出 |
| 等級 2 | 上傳、歷史紀錄、帳號管理（限等級 3）、修改密碼、登出 |
| 等級 3 | 上傳、我的紀錄、修改密碼、登出 |

### get_current_user（dependencies.py）

回傳的 dict 新增 `role` 欄位：`{"user_id": ..., "username": ..., "role": 1}`

### 註冊（POST /register）

自動設定角色：資料庫中無帳號 → role=1，有帳號 → role=3
