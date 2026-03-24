# 專案守則（Project Constitution）

## 專案概述

**名稱：** Meeting Minutes AI
**描述：** AI 驅動的會議紀錄應用程式，支援語音辨識、自動摘要與結構化輸出。

---

## 1. 技術棧原則

### 後端
- **語言：** Python 3.11+
- **框架：** FastAPI
- **AI 架構：** 策略模式（Strategy Pattern），透過抽象 `AudioProcessor` 介面支援模型抽換
  - **GeminiProvider（遠端）：** Google Gemini API，多模態一次產出全部結果
  - **LocalWhisperProvider（本地端）：** OpenAI Whisper，本地語音轉錄
- **依賴注入：** 透過 FastAPI `Depends` + 工廠函式動態實例化 Provider
- **套件管理：** uv
- **API 風格：** RESTful，回傳 JSON

### 前端
- **模板引擎：** Jinja2（伺服器端渲染）
- **動態互動：** HTMX
- **樣式框架：** Tailwind CSS（CDN）

### 資料儲存
- **資料庫：** SQLite（MVP），透過 SQLAlchemy ORM 確保未來可遷移
- **檔案儲存：** 本地檔案系統（uploads/ 目錄）

---

## 2. 程式碼品質標準

### 模組化設計
- 每個功能應獨立為一個模組（module），放置於對應的資料夾中
- 單一職責原則（SRP）：每個模組、類別、函式只負責一件事
- 模組間透過明確的介面（interface）溝通，降低耦合度
- **策略模式（Strategy Pattern）：** AI 處理模組必須實作 `AudioProcessor` 抽象介面，新增 Provider 不得修改現有程式碼（開放封閉原則）

### Docstring 規範
- **每個函式、類別、模組都必須有 Docstring**
- 使用 Google Style Docstring 格式
- 內容須包含：簡述、參數說明、回傳值說明
- 範例：

```python
async def process(self, file_path: str) -> ProcessingResult:
    """處理音檔，回傳統一格式的結果。

    透過具體 Provider（Gemini / Whisper）處理音檔，
    產出逐字稿、摘要與 Action Items。

    Args:
        file_path: 音訊檔案的路徑。

    Returns:
        包含逐字稿、摘要與待辦事項的 ProcessingResult。

    Raises:
        RateLimitError: API 頻率受限（429）。
        AuthenticationError: API Key 無效（401）。
        ProcessingError: 其他處理失敗。
    """
```

### 型別註解（Type Hints）
- 所有函式參數與回傳值必須加上型別註解
- 使用 `pydantic` 定義 API 的請求與回應模型

### 命名慣例
- **檔案與模組：** snake_case（例如 `audio_processor.py`）
- **類別：** PascalCase（例如 `TranscriptionService`）
- **函式與變數：** snake_case（例如 `process_audio`）
- **常數：** UPPER_SNAKE_CASE（例如 `MAX_FILE_SIZE`）

---

## 3. 專案結構原則

```
meeting-minutes-ai/
├── app/
│   ├── main.py              # FastAPI 應用入口
│   ├── config.py             # 設定管理
│   ├── database.py           # SQLAlchemy 引擎與 Session
│   ├── api/                  # API 路由層
│   │   └── routes/
│   ├── dependencies.py       # DI 工廠函式
│   ├── services/             # 業務邏輯層
│   │   ├── annotation_service.py  # TextGrid/RTTM 解析
│   │   └── providers/        # AudioProcessor 實作（策略模式）
│   ├── models/               # Pydantic / SQLAlchemy 資料模型
│   ├── core/                 # 核心工具（例外處理等）
│   ├── templates/            # Jinja2 HTML 模板
│   └── static/               # 靜態資源
├── uploads/                  # 上傳的音檔
├── tests/                    # 測試
├── constitution.md           # 本文件
├── pyproject.toml            # 專案設定與依賴
└── README.md
```

---

## 4. 測試標準

- 使用 `pytest` 作為測試框架
- 核心業務邏輯（services/）必須有單元測試
- API 路由使用 `httpx` + `TestClient` 進行整合測試
- 測試檔案命名：`test_<模組名稱>.py`
- 目標覆蓋率：≥ 80%

---

## 5. 錯誤處理

- 使用 FastAPI 的例外處理機制（`HTTPException`）
- 自定義例外類別統一放在 `app/core/exceptions.py`
- API 錯誤回應格式統一：

```json
{
  "detail": "錯誤描述",
  "error_code": "ERROR_CODE"
}
```

---

## 6. 版本控制

- 使用 Git 進行版本控制
- Commit message 使用 Conventional Commits 格式：
  - `feat:` 新功能
  - `fix:` 修復 Bug
  - `docs:` 文件更新
  - `refactor:` 重構
  - `test:` 測試相關
- 功能開發使用 feature branch，完成後合併至 main

---

## 7. 使用者體驗一致性

- API 回應格式保持一致（統一的 JSON 結構）
- 錯誤訊息應對使用者友善，避免暴露內部實作細節
- 長時間處理的操作（如音訊轉錄）應提供進度回饋機制

---

## 8. 安全性

- 敏感設定（API Key、密碼等）一律使用環境變數，不可寫死在程式碼中
- `.env` 檔案加入 `.gitignore`
- 上傳檔案須驗證格式與大小限制
