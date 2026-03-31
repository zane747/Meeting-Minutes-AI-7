# Research: 最新消息 / 公告訊息

## 技術背景

本功能完全使用既有技術棧，無需引入新依賴：

- **後端**：FastAPI + SQLAlchemy（async）+ Jinja2 模板
- **資料庫**：SQLite（透過 aiosqlite）
- **前端**：Tailwind CSS + 原生 JS（fetch API）
- **認證**：Session + Cookie（SessionMiddleware）

## 研究結論

### 1. 資料模型設計

- **Decision**：新增 `announcements` 表，結構參照既有的 `meetings` 表設計模式
- **Rationale**：與現有 ORM 模式一致（UUID 主鍵、created_by 外鍵關聯 User、時間戳欄位）
- **Alternatives considered**：複用 meetings 表加 type 欄位 → 否決，職責不同不應混用

### 2. 權限控制模式

- **Decision**：複用既有的 `require_role()` + 函式內 `_check_owner_permission` 模式
- **Rationale**：跟帳號管理、會議紀錄一致的權限架構，維護成本低
- **Alternatives considered**：建立通用權限中介層 → 過度設計，目前三個模組各自處理足夠

### 3. 路由結構

- **Decision**：頁面路由在 `pages.py` 新增，API 路由新增 `announcements.py`
- **Rationale**：遵循現有的關注點分離模式（頁面 vs API）
- **Alternatives considered**：全部寫在一個檔案 → 違反現有慣例

### 4. 前端搜尋

- **Decision**：前端 JS 即時篩選（與歷史紀錄頁一致）
- **Rationale**：公告數量假設為數百筆等級，前端篩選足夠，不需後端分頁
- **Alternatives considered**：後端分頁 + 搜尋 API → 目前規模不需要
