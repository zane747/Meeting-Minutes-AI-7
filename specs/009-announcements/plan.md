# 實施計畫：最新消息 / 公告訊息

## 技術背景

| 項目 | 值 |
|------|-----|
| 分支 | `009-announcements` |
| 規格 | `specs/009-announcements/spec.md` |
| 技術棧 | FastAPI + SQLAlchemy + Jinja2 + SQLite |
| 依賴 | 現有 User 模型、角色權限系統、認證機制 |

## 實施策略

遵循既有的架構模式，新增一個完整的公告 CRUD 模組：

1. **資料層**：新增 Announcement ORM 模型
2. **API 層**：新增 `announcements.py` API 路由（CRUD + 置頂）
3. **頁面層**：在 `pages.py` 新增公告頁面路由
4. **模板層**：新增公告列表頁、詳情頁、建立/編輯表單頁
5. **導覽列**：新增「最新消息」連結
6. **權限**：API 層全面套用權限檢查（吸取之前的教訓）

## 修改點清單

### 新增檔案

| 檔案 | 用途 |
|------|------|
| `app/api/routes/announcements.py` | 公告 API 路由（CRUD + 置頂） |
| `app/templates/announcements.html` | 公告列表頁 |
| `app/templates/announcement_detail.html` | 公告詳情頁 |
| `app/templates/announcement_form.html` | 建立/編輯公告表單 |

### 修改檔案

| 檔案 | 修改內容 |
|------|---------|
| `app/models/database_models.py` | 新增 Announcement 模型 |
| `app/models/schemas.py` | 新增公告相關 Pydantic 模型 |
| `app/main.py` | 註冊 announcements router |
| `app/api/routes/pages.py` | 新增公告頁面路由 |
| `app/templates/base.html` | 導覽列新增「最新消息」連結 |

## API 端點設計

| 方法 | 路徑 | 權限 | 用途 |
|------|------|------|------|
| GET | `/announcements` | 所有登入使用者 | 公告列表頁 |
| GET | `/announcements/create` | Role 1, 2 | 建立公告表單頁 |
| GET | `/announcements/{id}` | 所有登入使用者 | 公告詳情頁 |
| GET | `/announcements/{id}/edit` | 發布者或 Role 1 | 編輯公告表單頁 |
| POST | `/api/announcements` | Role 1, 2 | 建立公告 |
| PUT | `/api/announcements/{id}` | 發布者或 Role 1 | 編輯公告 |
| DELETE | `/api/announcements/{id}` | 發布者或 Role 1 | 刪除公告 |
| PUT | `/api/announcements/{id}/pin` | 僅 Role 1 | 切換置頂 |

## 權限檢查設計

吸取會議紀錄 API 權限漏洞的教訓，所有 API 端點從一開始就內建權限檢查：

- **`_check_announcement_owner`**：發布者本人或超級管理員（用於編輯、刪除）
- **頁面路由**：使用 `require_role()` 控制表單頁面存取
- **API 路由**：每個端點都有 `Depends(get_current_user)` + 函式內權限判斷

## 風險與注意事項

| 風險 | 應對 |
|------|------|
| 忘記在 API 層加權限檢查 | 參照 meetings.py 的 `_check_view_permission` 模式，建立時就加 |
| 資料庫 migration 問題 | SQLAlchemy 的 `create_all()` 會自動建新表，不影響既有資料 |
| 導覽列項目變多擠不下 | 目前 5 個連結（上傳、歷史、最新消息、帳號管理、管理中心），仍在合理範圍 |
