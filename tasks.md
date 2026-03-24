# 任務清單（Tasks）

> 根據 `spec.md`、`plan.md` 與 `constitution.md`，分解為具體可執行的任務。
> 依開發順序排列，每個階段的任務應依序完成。

---

## Phase 1：專案初始化

- [ ] **T-01** 初始化 Python 專案
  - 使用 `uv init` 建立專案
  - 設定 `pyproject.toml`（專案名稱、Python 版本、依賴）
  - 安裝核心依賴：fastapi, uvicorn, sqlalchemy, jinja2, python-dotenv, python-multipart, aiosqlite, pydub, pydantic-settings
  - 設定 optional dependencies：`local = ["openai-whisper"]`

- [ ] **T-02** 建立專案目錄結構
  - 建立 `app/` 及所有子目錄（api/routes, services/providers, models, core, templates, static）
  - 建立所有 `__init__.py`
  - 建立 `uploads/` 目錄
  - 建立 `tests/` 目錄與 `conftest.py`

- [ ] **T-03** 設定開發工具
  - 設定 Ruff（linter/formatter）於 `pyproject.toml`
  - 建立 `.gitignore`（含 .env, uploads/, __pycache__, *.db）
  - 建立 `.env.example`（所有環境變數範本）
  - 初始化 Git repo

- [ ] **T-04** 建立環境設定模組
  - 實作 `app/config.py`：使用 pydantic-settings 讀取 .env
  - 欄位：MODEL_MODE, GEMINI_API_KEY, GEMINI_MODEL, WHISPER_MODEL, OLLAMA_ENABLED, OLLAMA_BASE_URL, OLLAMA_MODEL, UPLOAD_DIR, MAX_FILE_SIZE_MB, DATABASE_URL

---

## Phase 2：資料層

- [ ] **T-05** 實作資料庫模組
  - 實作 `app/database.py`：SQLAlchemy async engine + session factory
  - 設定 SQLite 連線

- [ ] **T-06** 實作資料模型
  - 實作 `app/models/database_models.py`：
    - `Meeting` 模型（id, title, file_name, file_path, file_size, duration, status, provider, transcript, summary, error_message, created_at, updated_at）
    - `ActionItem` 模型（id, meeting_id, description, assignee, due_date, is_completed）
  - 實作狀態 Enum：`processing`, `completed`, `failed`

- [ ] **T-07** 實作 Pydantic Schemas
  - 實作 `app/models/schemas.py`：
    - `MeetingCreate`（上傳時的請求）
    - `MeetingResponse`（完整回應）
    - `MeetingStatusResponse`（狀態輪詢回應）
    - `ActionItemCreate` / `ActionItemUpdate` / `ActionItemResponse`
    - 注意：`ProcessingResult` 定義在 `providers/base.py`，不在此處重複

- [ ] **T-08** 建立資料庫初始化腳本
  - 在 `app/main.py` 的 startup event 中自動建表
  - 確認 SQLite 檔案自動建立

---

## Phase 3：策略模式核心架構

- [ ] **T-09** 實作 AudioProcessor 抽象介面
  - 實作 `app/services/providers/base.py`：
    - `ProcessingResult` dataclass
    - `AudioProcessor` ABC（process, get_provider_name, health_check）

- [ ] **T-10** 實作 GeminiProvider
  - 實作 `app/services/providers/gemini_provider.py`
  - 安裝 `google-generativeai` 依賴
  - 實作 `process()`：上傳音檔至 File API → 發送 Prompt → 解析 JSON
  - 實作 Prompt（段落式時間戳記逐字稿、Markdown 摘要、Action Items、建議標題，繁體中文）
  - 設定 `response_mime_type: "application/json"`
  - 實作 `health_check()`：測試 API Key 有效性
  - 實作錯誤分類：429 / 401 / 通用錯誤各自拋出對應例外

- [ ] **T-11** 實作 LocalWhisperProvider
  - 實作 `app/services/providers/local_whisper_provider.py`
  - 實作 Lazy Load + 類別層級快取（`_model = None`）
  - 實作 `process()`：載入模型 → 轉錄音檔 → 帶時間戳記段落式逐字稿（保留原語言）
  - 實作 Ollama 可選摘要：檢查 OLLAMA_ENABLED → 呼叫 Ollama API 生成摘要與 Actions
  - 實作 `health_check()`：檢查 whisper 套件 + 模型可用性 + Ollama 連通性（若啟用）

- [ ] **T-12** 實作自定義例外
  - 實作 `app/core/exceptions.py`：
    - `ProviderUnavailableError`
    - `RateLimitError`
    - `AuthenticationError`
    - `ProcessingError`

- [ ] **T-13** 實作依賴注入工廠
  - 實作 `app/dependencies.py`：
    - `get_audio_processor(mode: str | None = Query(None))`：根據前端參數或 MODEL_MODE 環境變數實例化 Provider
    - `get_db()`：取得資料庫 Session

---

## Phase 4：業務邏輯層

- [ ] **T-14** 實作 AudioService
  - 實作 `app/services/audio_service.py`：
    - `validate_file()`：驗證檔案格式（mp3/wav）與大小（≤ 100MB）
    - `save_file()`：儲存至 uploads/ 目錄
    - `get_duration()`：使用 pydub 取得音檔時長
    - `delete_audio_file()`：刪除音檔，更新 DB file_path 為 null

- [ ] **T-15** 實作 MeetingProcessor
  - 實作 `app/services/meeting_processor.py`：
    - `process_meeting()`：協調層，呼叫 Provider 並儲存結果至 DB
    - 處理前執行 `health_check()`
    - 處理成功：儲存 transcript、summary、action_items，更新 status=completed
    - 處理失敗：依錯誤類型儲存 error_message，更新 status=failed
    - 若使用者未填標題，使用 AI 建議標題

---

## Phase 5：API 路由層

- [ ] **T-16** 實作主 API：上傳 + 處理
  - 實作 `POST /api/meetings/upload-and-process`
  - 接收 multipart form：file, title(optional), mode(optional)
  - 呼叫 AudioService 驗證 + 儲存
  - 寫入 DB → 送入 BackgroundTask → 回傳 meeting_id

- [ ] **T-17** 實作狀態查詢 API
  - 實作 `GET /api/meetings/{id}/status`
  - 回傳：status, provider, error_message（供 HTMX polling）

- [ ] **T-18** 實作重試 API
  - 實作 `POST /api/meetings/{id}/retry`
  - 接受 `?mode=` 參數允許切換 Provider
  - 更新 provider 欄位 → 重新送入 BackgroundTask

- [ ] **T-19** 實作會議 CRUD API
  - `GET /api/meetings` — 列表（時間倒序）
  - `GET /api/meetings/{id}` — 單筆詳情
  - `PUT /api/meetings/{id}` — 編輯標題/摘要/逐字稿
  - `DELETE /api/meetings/{id}` — 刪除會議紀錄（含音檔）
  - `DELETE /api/meetings/{id}/audio` — 僅刪除音檔

- [ ] **T-20** 實作 Action Items CRUD API
  - `POST /api/meetings/{id}/actions` — 新增
  - `PUT /api/meetings/{id}/actions/{action_id}` — 編輯（含完成狀態）
  - `DELETE /api/meetings/{id}/actions/{action_id}` — 刪除

- [ ] **T-21** 實作啟動時健康檢查
  - 在 `app/main.py` 的 startup event 中：
    - 建立資料庫表
    - 檢查預設 Provider 可用性（warning log）
    - 建立 uploads/ 目錄（若不存在）

---

## Phase 6：前端模板

- [ ] **T-22** 實作 base.html 共用模板
  - 引入 Tailwind CSS（CDN）
  - 引入 HTMX（CDN）
  - 共用 header/nav（首頁 / 歷史紀錄）
  - 響應式 layout

- [ ] **T-23** 實作首頁（index.html）— 上傳頁
  - 檔案選擇器（accept=".mp3,.wav"）
  - 前端驗證：格式、大小
  - 瀏覽器 API 取得音檔時長並顯示
  - 會議標題輸入框（選填）
  - Provider 選擇器（radio: 遠端/本地端）
  - 「開始」按鈕 → HTMX POST 上傳 + 處理
  - 上傳進度條

- [ ] **T-24** 實作結果頁（meeting.html）
  - HTMX polling：每 2 秒查詢狀態
  - 處理中：顯示動畫 + Provider 名稱
  - 完成後：
    - 逐字稿區塊（Markdown 純文字可編輯）
    - 摘要區塊（Markdown 純文字可編輯，本地端未配置 Ollama 時隱藏並顯示提示）
    - Action Items 列表（可編輯/新增/刪除/標記完成）
    - 「儲存」按鈕
    - 「刪除音檔」按鈕
  - 失敗時：錯誤訊息（依類型）+ 重試按鈕（含 Provider 切換選項）

- [ ] **T-25** 實作歷史紀錄頁（history.html）
  - 會議列表（時間倒序）
  - 每筆顯示：標題、檔案名稱、時長、狀態、Provider、建立時間
  - 點擊可跳轉至結果頁
  - 刪除按鈕（瀏覽器 confirm 確認）

- [ ] **T-26** 實作頁面路由
  - 實作 `app/api/routes/pages.py`：
    - `GET /` → index.html
    - `GET /meetings/{id}` → meeting.html
    - `GET /meetings` → history.html

---

## Phase 7：測試

- [ ] **T-27** 撰寫 AudioService 單元測試
  - 測試檔案格式驗證（通過/拒絕）
  - 測試檔案大小驗證
  - 測試檔案儲存與刪除

- [ ] **T-28** 撰寫 Provider 單元測試
  - `test_gemini_provider.py`：mock API 呼叫，驗證 JSON 解析、錯誤分類
  - `test_local_whisper_provider.py`：mock whisper 模型，驗證 Lazy Load、時間戳記格式

- [ ] **T-29** 撰寫 MeetingProcessor 單元測試
  - mock Provider，驗證協調流程
  - 驗證成功/失敗時的 DB 狀態更新
  - 驗證標題自動生成邏輯

- [ ] **T-30** 撰寫 API 整合測試
  - 使用 TestClient + mock Provider
  - 測試上傳 + 處理流程
  - 測試狀態查詢
  - 測試重試（含 Provider 切換）
  - 測試 CRUD 操作
  - 測試錯誤回應格式

---

## Phase 8：收尾

- [ ] **T-31** 端到端驗證
  - 使用真實音檔測試 GeminiProvider 完整流程
  - 使用真實音檔測試 LocalWhisperProvider 完整流程
  - 驗證 Ollama 摘要（若已配置）
  - 驗證前端所有頁面在桌面與手機上的顯示

- [ ] **T-32** 建立 README.md
  - 專案簡介
  - 快速開始指南（安裝、設定 .env、啟動）
  - Provider 切換說明
  - Ollama 配置說明

---

## 任務依賴關係

```
Phase 1（T-01~T-04）
    └──▶ Phase 2（T-05~T-08）
            └──▶ Phase 3（T-09~T-13）
                    └──▶ Phase 4（T-14~T-15）
                            └──▶ Phase 5（T-16~T-21）
                                    └──▶ Phase 6（T-22~T-26）
Phase 3 完成後可同步開始 ──▶ Phase 7（T-27~T-30）
所有 Phase 完成後 ──▶ Phase 8（T-31~T-32）
```

---

## 任務統計

| Phase | 任務數 | 說明 |
|-------|--------|------|
| Phase 1 | 4 | 專案初始化 |
| Phase 2 | 4 | 資料層 |
| Phase 3 | 5 | 策略模式核心 |
| Phase 4 | 2 | 業務邏輯 |
| Phase 5 | 6 | API 路由 |
| Phase 6 | 5 | 前端模板 |
| Phase 7 | 4 | 測試 |
| Phase 8 | 2 | 收尾 |
| **合計** | **32** | |
