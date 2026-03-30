# API Contracts: 帳號管理

---

## 新增端點

### 1. 帳號管理頁面

```
GET /accounts
```

| 項目 | 說明 |
|------|------|
| 用途 | 顯示帳號列表頁面 |
| 認證 | ✅ 需要登入 |
| 回應 | HTML 頁面（accounts.html），包含所有帳號的列表 |

---

### 2. 修改密碼頁面

```
GET /accounts/change-password
```

| 項目 | 說明 |
|------|------|
| 用途 | 顯示修改密碼表單 |
| 認證 | ✅ 需要登入 |
| 回應 | HTML 頁面（change_password.html） |

---

### 3. 處理修改密碼

```
POST /accounts/change-password
```

| 項目 | 說明 |
|------|------|
| 用途 | 驗證舊密碼 → 更新為新密碼 |
| 認證 | ✅ 需要登入 |
| Content-Type | `application/x-www-form-urlencoded` |

**請求欄位**:

| 欄位 | 型別 | 必填 | 驗證 |
|------|------|------|------|
| `old_password` | string | 是 | 必須與資料庫中的密碼雜湊值匹配 |
| `new_password` | string | 是 | 至少 8 字元 |

**回應（成功）**: 重新渲染 change_password.html，帶成功訊息
**回應（失敗）**: 重新渲染 change_password.html，帶錯誤訊息

---

### 4. 停用/啟用帳號

```
POST /api/accounts/{user_id}/toggle-active
```

| 項目 | 說明 |
|------|------|
| 用途 | 切換帳號的啟用/停用狀態 |
| 認證 | ✅ 需要登入 |
| 回應 | JSON（成功訊息 + 新狀態） |

**保護規則**:
- 不能操作自己的帳號 → 403
- 操作後啟用帳號數量 < 1 → 403
- 找不到帳號 → 404

---

### 5. 刪除帳號

```
DELETE /api/accounts/{user_id}
```

| 項目 | 說明 |
|------|------|
| 用途 | 刪除帳號（前端需先二次確認） |
| 認證 | ✅ 需要登入 |
| 回應 | JSON（成功訊息） |

**保護規則**:
- 不能刪除自己 → 403
- 刪除後啟用帳號數量 < 1 → 403
- 找不到帳號 → 404

---

## 修改的端點

### get_current_user（dependencies.py）

新增 `is_active` 檢查：從 session 讀到 user_id 後，去資料庫確認帳號仍為啟用狀態。如果已被停用，清除 session 並導向登入頁。

---

## 導覽列修改（base.html）

- 新增「帳號管理」連結 → `/accounts`
- 使用者名稱旁新增「修改密碼」連結 → `/accounts/change-password`
