# Research: 權限管理

---

## 決策 1：角色存儲方式

**Decision**: 在 User 表新增 `role` 整數欄位（1/2/3）

**Rationale**:
- 只有 3 個固定等級，不需要獨立的 Role 資料表
- 整數比較比字串比較快（`role <= 2` 比 `role in ["admin", "super_admin"]` 簡潔）
- 數字天然有大小關係：1 > 2 > 3（等級越小權限越高）

**Alternatives considered**:
| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| 獨立 Role 表（多對多） | 彈性最高 | 只有 3 個角色，過度設計 | ❌ |
| 字串欄位（"admin"/"user"） | 好讀 | 無法用 <= 做等級比較 | ❌ |
| 整數欄位（1/2/3） | 簡單、可比較、效能好 | 可讀性稍差（需查對照表） | ✅ |

---

## 決策 2：權限檢查機制

**Decision**: 新增 `require_role(max_level)` 依賴函式

**Rationale**:
- 沿用現有的 `Depends()` 模式
- `require_role(1)` = 只有等級 1 可以用
- `require_role(2)` = 等級 1 和 2 都可以用（因為 1 <= 2）
- 一行程式碼就能控制路由的權限

**How it works**:
```
路由加上 Depends(require_role(2))
    → 先執行 get_current_user（檢查登入）
    → 再檢查 user.role <= 2（等級夠高）
    → 通過 → 路由正常執行
    → 不通過 → 403 Forbidden
```

---

## 決策 3：會議可見性的查詢策略

**Decision**: 在查詢會議列表時，根據當前使用者角色和可見性欄位動態組合 SQL 條件

**Rationale**:
- 等級 1：不加任何條件（看全部）
- 等級 2：`WHERE (created_by = 自己) OR (visibility = 'public') OR (建立者角色 = 3) OR (visibility = 'same_level' AND 建立者角色 = 2)`
- 等級 3：`WHERE (created_by = 自己) OR (visibility = 'public') OR (visibility = 'same_level' AND 建立者角色 = 3)`

---

## 決策 4：管理中心頁面

**Decision**: 等級 1 的管理中心整合帳號管理 + 所有會議紀錄在同一個頁面

**Rationale**:
- 帳號管理（/accounts）已存在，管理中心可以直接連結過去
- 管理中心的獨特功能是「看到所有人的會議 + 角色變更」
- 不需要重做帳號管理頁面，只需在管理中心加入角色變更功能和全域會議列表

---

## 決策 5：第一個帳號自動成為等級 1

**Decision**: 在 `auth_service.create_user()` 中檢查使用者數量，若為 0 則設 role=1

**Rationale**:
- 最簡單的做法，不需要額外的初始化腳本
- 只在註冊時判斷一次，不影響效能
