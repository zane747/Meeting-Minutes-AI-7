# 技術實施計畫（Technical Plan）

> 根據 `constitution.md` 與 `spec.md`，制定 Meeting Minutes AI 的技術架構與實施方案。

---

## 1. 技術棧選擇

### 後端

| 技術 | 用途 | 選擇理由 |
|------|------|----------|
| **Python 3.11+** | 主要語言 | 豐富的 AI 生態系，與 Google AI / Whisper SDK 原生整合 |
| **FastAPI** | Web 框架 | 非同步支援、自動 API 文件、Pydantic 整合、依賴注入原生支援 |
| **Google Gemini API** | 遠端 AI Provider | 原生多模態，單次呼叫同時處理轉錄、摘要、Action Items |
| **OpenAI Whisper** | 本地端 AI Provider | 開源、可離線使用、資料不出站 |
| **SQLite** | 資料庫 | MVP 階段輕量首選，零配置，未來可遷移至 PostgreSQL |
| **SQLAlchemy** | ORM | Python 主流 ORM，支援多種資料庫，方便未來遷移 |

### 前端

| 技術 | 用途 | 選擇理由 |
|------|------|----------|
| **Jinja2 Templates** | 伺服器端渲染 | MVP 快速開發，無需額外前端建置流程 |
| **HTMX** | 動態互動 | 無需寫 JavaScript 即可實現 AJAX、進度更新等互動 |
| **Tailwind CSS (CDN)** | 樣式框架 | 快速建立響應式介面，CDN 引入免建置 |

### 開發工具

| 技術 | 用途 |
|------|------|
| **uv** | Python 套件管理 |
| **pytest** | 測試框架 |
| **Ruff** | Linter / Formatter |

---

## 2. 系統架構：策略模式（Strategy Pattern）

### 2.1 架構總覽

```
┌──────────────────────────────────────────────────────────────┐
│                       Web 瀏覽器（前端）                       │
│    Jinja2 Templates + HTMX + Tailwind CSS                    │
└──────────────┬────────────────────────────┬──────────────────┘
               │ HTTP                       │ HTMX Polling
               ▼                            ▼
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI 應用伺服器                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │  API Routes   │  │  Page Routes  │                         │
│  │  (REST API)   │  │  (HTML 頁面)  │                         │
│  └───────┬──────┘  └───────┬──────┘                          │
│          │                 │                                 │
│          ▼                 ▼                                 │
│  ┌───────────────────────────────────────────────────────┐   │
│  │                Services（業務邏輯層）                   │   │
│  │                                                       │   │
│  │  ┌──────────────┐  ┌──────────────────────────────┐   │   │
│  │  │ AudioService │  │ MeetingProcessor             │   │   │
│  │  │ (上傳/驗證)   │  │ (協調層，呼叫 Provider)       │   │   │
│  │  └──────────────┘  └──────────┬───────────────────┘   │   │
│  │                               │                       │   │
│  │                    ┌──────────┴───────────┐            │   │
│  │                    │  AudioProcessor      │            │   │
│  │                    │  (抽象介面/Protocol)   │            │   │
│  │                    └──────────┬───────────┘            │   │
│  │                    ┌─────────┴──────────┐              │   │
│  │                    │                    │              │   │
│  │           ┌────────▼───────┐  ┌────────▼──────────┐   │   │
│  │           │ GeminiProvider │  │ LocalWhisper       │   │   │
│  │           │ (遠端多模態)    │  │ Provider           │   │   │
│  │           │                │  │ (本地端 Whisper)    │   │   │
│  │           └────────┬───────┘  └────────┬──────────┘   │   │
│  │                    │                    │              │   │
│  └────────────────────┼────────────────────┼──────────────┘   │
└───────────┬───────────┼────────────────────┼─────────────────┘
            │           │                    │
            ▼           ▼                    ▼
  ┌──────────────┐ ┌──────────┐    ┌─────────────────┐
  │  SQLite (DB) │ │ Gemini   │    │ Local Whisper    │
  │  會議紀錄     │ │ API      │    │ Model            │
  └──────────────┘ │ (雲端)    │    │ (本地 GPU/CPU)   │
                   └──────────┘    └─────────────────┘
```

### 2.2 策略模式核心設計

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProcessingResult:
    """AI 處理結果的統一資料結構。"""

    suggested_title: str | None
    transcript: str
    summary: str
    action_items: list[dict]


class AudioProcessor(ABC):
    """音檔處理的抽象介面（Strategy Interface）。

    所有 Provider 必須實作此介面，確保主程式與具體模型實作解耦。
    """

    @abstractmethod
    async def process(self, file_path: str) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        Args:
            file_path: 音訊檔案的路徑。

        Returns:
            包含逐字稿、摘要與待辦事項的結構化結果。
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """回傳 Provider 名稱，用於日誌與 UI 顯示。"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """檢查 Provider 是否可用（API 連通性、模型可用性）。"""
        ...
```

### 2.3 雙軌 Provider 實作

#### GeminiProvider（遠端）

```python
class GeminiProvider(AudioProcessor):
    """透過 Gemini API 處理音檔（遠端多模態）。

    利用 Gemini 原生多模態能力，將音檔直接傳送至 API，
    單一 Prompt 同時回傳逐字稿、摘要與 Action Items。
    """

    async def process(self, file_path: str) -> ProcessingResult:
        # 1. 上傳音檔至 Gemini File API
        # 2. 發送 Prompt，要求回傳結構化 JSON
        # 3. 解析回應，回傳 ProcessingResult
        ...

    def get_provider_name(self) -> str:
        return "Gemini API (Remote)"
```

#### LocalWhisperProvider（本地端）

```python
class LocalWhisperProvider(AudioProcessor):
    """透過本地端 Whisper 模型處理音檔。

    使用 OpenAI Whisper 進行語音轉錄（Lazy Load + 快取模式）。
    逐字稿保留原始語言，不強制轉為繁體中文。
    若已配置 Ollama，可選配本地摘要功能。
    """

    _model = None  # 類別層級快取，Lazy Load

    async def process(self, file_path: str) -> ProcessingResult:
        # 1. Lazy Load：若 _model 為 None，載入並快取
        # 2. 轉錄音檔，產出帶時間戳記的文字（保留原始語言）
        # 3. 若 Ollama 可用，呼叫本地 LLM 生成摘要與 Action Items
        # 4. 回傳 ProcessingResult
        ...

    def get_provider_name(self) -> str:
        return "Whisper (Local)"
```

### 2.4 依賴注入（Dependency Injection）

透過 FastAPI 原生的 `Depends` 機制實現 Provider 的動態切換：

```python
# app/dependencies.py

from app.config import settings
from app.services.providers.base import AudioProcessor
from app.services.providers.gemini_provider import GeminiProvider
from app.services.providers.local_whisper_provider import LocalWhisperProvider


def get_audio_processor() -> AudioProcessor:
    """根據 MODEL_MODE 環境變數，實例化對應的 Provider。

    Returns:
        AudioProcessor 的具體實作。

    Raises:
        ValueError: 當 MODEL_MODE 設定值無效時。
    """
    if settings.MODEL_MODE == "remote":
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )
    elif settings.MODEL_MODE == "local":
        return LocalWhisperProvider(
            model_size=settings.WHISPER_MODEL,
        )
    else:
        raise ValueError(f"未知的 MODEL_MODE: {settings.MODEL_MODE}")
```

在 API Route 中注入：

```python
# app/api/routes/meetings.py

@router.post("/{meeting_id}/process")
async def process_meeting(
    meeting_id: str,
    processor: AudioProcessor = Depends(get_audio_processor),
    db: Session = Depends(get_db),
):
    """觸發 AI 處理，使用注入的 Provider。"""
    ...
```

### 2.5 前端動態切換（可選）

除了環境變數外，前端上傳頁可提供 Provider 選擇器：

```
┌─────────────────────────────────┐
│  會議紀錄 AI                     │
│                                 │
│  [選擇檔案]  meeting_recording.mp3│
│  時長：15:32  大小：12.3 MB      │
│                                 │
│  會議標題（選填）：_______________  │
│                                 │
│  處理模式：                      │
│  ○ 遠端（Gemini API）  ← 預設    │
│  ○ 本地端（Whisper + Ollama）    │
│                                 │
│  [開始]  ← 一鍵上傳 + 處理       │
└─────────────────────────────────┘
```

前端選擇透過 API 參數 `?mode=remote|local` 傳遞，覆寫環境變數預設值：

```python
def get_audio_processor(mode: str | None = Query(None)) -> AudioProcessor:
    """根據前端參數或環境變數，決定使用哪個 Provider。"""
    effective_mode = mode or settings.MODEL_MODE
    ...
```

---

## 3. 資料模型設計

### Meeting（會議紀錄）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | UUID | 主鍵 |
| `title` | String (nullable) | 會議標題（選填，AI 可自動生成） |
| `file_name` | String | 原始檔案名稱 |
| `file_path` | String (nullable) | 音檔儲存路徑（刪除音檔後設為 null） |
| `file_size` | Integer | 檔案大小（bytes） |
| `duration` | Float | 音檔時長（秒） |
| `status` | Enum | `processing` / `completed` / `failed` |
| `provider` | String (nullable) | 使用的 Provider 名稱（`remote` / `local`） |
| `transcript` | Text (nullable) | 段落式時間戳記逐字稿 |
| `summary` | Text (nullable) | AI 生成的會議摘要（Markdown） |
| `error_message` | String (nullable) | 失敗時的錯誤訊息 |
| `created_at` | DateTime | 建立時間 |
| `updated_at` | DateTime | 更新時間 |

### ActionItem（待辦事項）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | UUID | 主鍵 |
| `meeting_id` | UUID | 外鍵，關聯 Meeting |
| `description` | String | 任務描述 |
| `assignee` | String (nullable) | 負責人 |
| `due_date` | String (nullable) | 截止日期 |
| `is_completed` | Boolean | 是否已完成 |

### 狀態機

```
processing ──▶ completed
    │
    └──▶ failed（可手動重試 → processing）
```

> 一步驟流程下，建立 Meeting 時直接進入 `processing`，不需要 `uploaded` 中間狀態。

---

## 4. API 端點設計

### 頁面路由（HTML）

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/` | 首頁（上傳頁面，含 Provider 選擇） |
| `GET` | `/meetings/{id}` | 結果頁（逐字稿 + 摘要 + Action Items） |
| `GET` | `/meetings` | 歷史紀錄頁（依時間倒序） |

### REST API

| 方法 | 路徑 | 說明 |
|------|------|------|
| `POST` | `/api/meetings/upload-and-process?mode=remote\|local` | 一步驟：上傳音檔 + 自動觸發 AI 處理 |
| `POST` | `/api/meetings/{id}/retry?mode=remote\|local` | 失敗後重新觸發（允許切換 Provider） |
| `GET` | `/api/meetings/{id}/status` | 查詢處理狀態（供 HTMX polling） |
| `GET` | `/api/meetings/{id}` | 取得完整會議資料 |
| `PUT` | `/api/meetings/{id}` | 編輯會議（標題、摘要、逐字稿） |
| `POST` | `/api/meetings/{id}/actions` | 新增 Action Item |
| `PUT` | `/api/meetings/{id}/actions/{action_id}` | 編輯 Action Item |
| `DELETE` | `/api/meetings/{id}/actions/{action_id}` | 刪除 Action Item |
| `DELETE` | `/api/meetings/{id}` | 刪除會議紀錄 |
| `DELETE` | `/api/meetings/{id}/audio` | 刪除音檔（保留文字紀錄） |

---

## 5. 核心處理流程

### 5.1 一步驟上傳 + 處理流程

```
使用者選擇音檔（+ 選填標題 + 選擇 Provider）→ 按下「開始」
→ 前端驗證格式/大小，前端透過瀏覽器 API 取得音檔時長
→ POST /api/meetings/upload-and-process?mode=remote
→ 後端驗證（MIME type、大小）
→ 儲存至 uploads/
→ 寫入 DB（status: processing, provider=remote|local, duration=前端傳來的時長）
→ 回傳 meeting_id，前端跳轉至結果頁（輪詢模式）
→ 送入 BackgroundTask：
    0. 執行 processor.health_check()，失敗則報錯
    ┌─────────────────────────────────────────────────┐
    │  processor.process(file_path)                   │
    │                                                 │
    │  ┌─ GeminiProvider ─────────────────────────┐   │
    │  │ 1. 上傳音檔至 Gemini File API             │   │
    │  │ 2. 發送多模態 Prompt                      │   │
    │  │ 3. 解析 JSON → ProcessingResult           │   │
    │  │    (transcript + summary + action_items)  │   │
    │  └──────────────────────────────────────────┘   │
    │                                                 │
    │  ┌─ LocalWhisperProvider ───────────────────┐   │
    │  │ 1. Lazy Load Whisper 模型（首次載入後快取） │   │
    │  │ 2. 轉錄音檔 → 帶時間戳記文字（原始語言）    │   │
    │  │ 3. 若 Ollama 可用 → 生成摘要 + Actions    │   │
    │  │ 4. 回傳 ProcessingResult                  │   │
    │  └──────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────┘
→ 儲存 ProcessingResult 至 DB
→ 更新 status: completed
* 失敗時：
  - 429 Rate Limit → error_message: "API 頻率受限，請稍候或切換本地模式"
  - 401 Unauthorized → error_message: "API Key 設定錯誤，請檢查 .env 設定"
  - 其他錯誤 → 通用錯誤訊息
  - 更新 status: failed
```

### 5.2 前端狀態輪詢

```
前端透過 HTMX 每 2 秒 GET /api/meetings/{id}/status
→ status: processing → 顯示處理中動畫 + 使用的 Provider 名稱
→ status: completed → 停止輪詢，載入完整結果頁
→ status: failed → 停止輪詢，顯示錯誤訊息（依錯誤類型）與重試按鈕
                   重試按鈕允許切換 Provider（?mode=local|remote）
```

### 5.3 結果頁渲染邏輯

```
載入 Meeting 資料
→ 顯示逐字稿區塊（一律顯示）
→ 檢查 summary 是否為空：
  - 有值 → 顯示摘要區塊
  - 空值 + provider=local + Ollama 未配置 → 隱藏摘要區塊，顯示「配置 Ollama 以啟用本地摘要」
  - 空值 + provider=remote → 顯示「摘要生成失敗」
→ 檢查 action_items 是否為空：同上邏輯
```

---

## 6. Provider 整合細節

### 6.1 GeminiProvider — Prompt 設計

```
你是一位專業的會議記錄助理。請分析以下音檔，並以 JSON 格式回傳：

1. transcript：逐字稿，以段落式時間戳記呈現（格式：[MM:SS - MM:SS] 內容）
2. summary：會議摘要（Markdown 格式），包含：
   - 會議主題
   - 重點討論事項
   - 決議事項
3. action_items：待辦事項列表，每項包含 description、assignee（若無法辨識則為 null）、due_date（若未提及則為 null）
4. suggested_title：根據會議內容建議一個簡短標題

所有輸出必須使用繁體中文。

請嚴格以下列 JSON 格式回傳：
{
  "suggested_title": "...",
  "transcript": "...",
  "summary": "...",
  "action_items": [...]
}
```

### 6.2 GeminiProvider — API 呼叫

- SDK：`google-generativeai`
- 模型：`gemini-1.5-flash`（預設）或 `gemini-1.5-pro`
- 音檔透過 Gemini File API 上傳
- 設定 `response_mime_type: "application/json"` 確保結構化輸出

### 6.3 LocalWhisperProvider — 處理方式

- SDK：`openai-whisper`
- 模型大小：透過 `WHISPER_MODEL` 環境變數設定（`base` / `small` / `medium` / `large`）
- **模型載入策略：** Lazy Load + 快取（第一次呼叫時載入，之後駐留記憶體至程式關閉）
- 逐字稿輸出：帶時間戳記，**保留原始語言**（不強制繁體中文）
- **Ollama 摘要（可選配）：**
  - 若 `OLLAMA_ENABLED=true` 且 Ollama 服務可連通 → 呼叫本地 LLM 生成摘要與 Action Items
  - 若未配置 → summary 與 action_items 回傳空值，前端顯示提示訊息

### 6.4 Ollama 摘要 Prompt 設計

當 `OLLAMA_ENABLED=true` 且 Ollama 可連通時，LocalWhisperProvider 將 Whisper 逐字稿傳送至 Ollama（Gemma 2 9B），透過以下 Prompt 生成摘要與 Action Items：

```
你是一位專業的會議記錄助理。以下是一段會議的逐字稿，請分析後以 JSON 格式回傳：

1. summary：會議摘要（Markdown 格式），包含：
   - 會議主題
   - 重點討論事項
   - 決議事項
2. action_items：待辦事項列表，每項包含 description、assignee（若無法辨識則為 null）、due_date（若未提及則為 null）
3. suggested_title：根據會議內容建議一個簡短標題

所有輸出必須使用繁體中文。

逐字稿：
{transcript}

請嚴格以下列 JSON 格式回傳：
{
  "suggested_title": "...",
  "summary": "...",
  "action_items": [
    {"description": "...", "assignee": "..." or null, "due_date": "..." or null}
  ]
}
```

**API 呼叫方式：**
- 使用 `httpx` 直接呼叫 Ollama REST API（`POST {OLLAMA_BASE_URL}/api/generate`）
- 不額外安裝 Ollama 客戶端套件
- 設定 `"format": "json"` 確保結構化輸出
- 模型：`gemma2:9b`（透過 `OLLAMA_MODEL` 環境變數設定）

---

### 6.5 Provider 健康檢查機制

**啟動時（Startup Event）：**
```python
@app.on_event("startup")
async def check_providers():
    """啟動時偵測已配置的 Provider 可用性。"""
    processor = get_audio_processor()
    is_healthy = await processor.health_check()
    if not is_healthy:
        logger.warning(f"Provider {processor.get_provider_name()} 不可用")
```

**執行時（每次處理前）：**
```python
# 在 BackgroundTask 中，process() 前先確認
if not await processor.health_check():
    meeting.status = "failed"
    meeting.error_message = f"{processor.get_provider_name()} 無法連線"
    return
```

**各 Provider 的 health_check 實作：**
- **GeminiProvider：** 測試 API Key 有效性（輕量 API 呼叫）
- **LocalWhisperProvider：** 檢查 `whisper` 套件是否已安裝 + 模型檔案是否存在
- **Ollama（若啟用）：** 呼叫 `http://localhost:11434/api/tags` 確認服務存活

### 6.6 錯誤分類與提示

| 錯誤類型 | HTTP Status | 使用者提示 |
|----------|-------------|-----------|
| Gemini 429 Rate Limit | 429 | 「API 頻率受限，請稍候或切換本地模式」 |
| Gemini 401 Unauthorized | 401 | 「API Key 設定錯誤，請檢查 .env 設定」 |
| Whisper 未安裝 | - | 「Whisper 未安裝，請執行 `pip install openai-whisper` 或切換遠端模式」 |
| Ollama 未連通 | - | 「Ollama 服務未啟動，本地摘要功能不可用」 |
| 通用錯誤 | 500 | 「處理失敗，請重試或切換處理模式」 |

---

## 7. 專案目錄結構

```
meeting-minutes-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 應用入口與設定
│   ├── config.py                   # 環境變數與設定管理
│   ├── database.py                 # SQLAlchemy 引擎與 Session
│   ├── dependencies.py             # DI 工廠：get_audio_processor()
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── meetings.py         # 會議相關 REST API
│   │       └── pages.py            # HTML 頁面路由
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_service.py        # 音檔上傳、驗證、元資料提取
│   │   ├── meeting_processor.py    # 協調層：呼叫 Provider 並儲存結果
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py             # AudioProcessor 抽象介面 + ProcessingResult
│   │       ├── gemini_provider.py  # GeminiProvider 實作
│   │       └── local_whisper_provider.py  # LocalWhisperProvider 實作
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database_models.py      # SQLAlchemy ORM 模型
│   │   └── schemas.py              # Pydantic 請求/回應模型
│   ├── core/
│   │   ├── __init__.py
│   │   └── exceptions.py           # 自定義例外
│   ├── templates/                   # Jinja2 HTML 模板
│   │   ├── base.html
│   │   ├── index.html               # 上傳頁（含 Provider 選擇）
│   │   ├── meeting.html             # 結果頁
│   │   └── history.html             # 歷史紀錄頁
│   └── static/                      # 靜態資源（CSS / JS）
├── uploads/                         # 上傳的音檔儲存目錄
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # 測試 fixtures（含 mock Provider）
│   ├── test_audio_service.py
│   ├── test_gemini_provider.py
│   ├── test_local_whisper_provider.py
│   ├── test_meeting_processor.py
│   └── test_api.py
├── .env.example
├── .gitignore
├── constitution.md
├── spec.md
├── plan.md                          # 本文件
├── clarify.md
├── pyproject.toml
└── README.md
```

---

## 8. 關鍵技術決策

| 決策 | 方案 | 理由 |
|------|------|------|
| 架構模式 | **策略模式（Strategy Pattern）** | 主程式與模型實作解耦，支援動態切換 Provider |
| 依賴注入 | **FastAPI Depends** | 框架原生支援，無需額外 DI 容器 |
| 預設 Provider | **GeminiProvider（remote）** | 功能最完整，一次產出所有結果 |
| 本地 Provider | **LocalWhisperProvider** | 離線使用、資料不出站、可選配 Ollama 摘要 |
| 切換機制 | **環境變數 + 前端參數** | 環境變數設定預設值，前端可覆寫 |
| Whisper 載入 | **Lazy Load + 快取** | 首次使用時載入，駐留至程式關閉 |
| 本地端語言 | **保留原始語言** | 不強制繁體中文，未來串接 LLM 翻譯 |
| 健康檢查 | **啟動時 + 執行時雙重檢查** | 啟動 warning、執行前確認可用性 |
| UX 流程 | **一步驟（上傳 + 處理合併）** | 簡單有力，減少操作步驟 |
| 重試切換 | **允許切換 Provider 重試** | Gemini 429 時可改用本地模式 |
| 刪除確認 | **瀏覽器 confirm 對話框** | 簡單直覺 |
| 錯誤分類 | **依 HTTP 狀態碼區分提示** | 429/401/通用錯誤各自對應不同訊息 |
| 背景任務 | **FastAPI BackgroundTasks** | MVP 內建方案，規模增長後再遷移至 Celery |
| 資料庫 | **SQLite → PostgreSQL** | MVP 用 SQLite 零配置，透過 SQLAlchemy 確保可遷移 |
| 前端方案 | **Jinja2 + HTMX** | 避免前後端分離的複雜度，Python 全棧開發 |
| 並行處理 | **單一佇列，不並行** | MVP 簡化，避免 API 配額競爭與記憶體問題 |

---

## 9. 環境變數

```env
# .env.example

# === Provider 切換 ===
MODEL_MODE=remote                    # remote / local（預設使用的 Provider）

# === Gemini（遠端模式）===
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash        # gemini-1.5-flash / gemini-1.5-pro

# === Whisper（本地模式）===
WHISPER_MODEL=base                   # tiny / base / small / medium / large

# === Ollama（本地摘要，可選）===
OLLAMA_ENABLED=false                 # true / false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:9b                # 本地 LLM 模型名稱（Gemma 2 9B）

# === 通用 ===
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=100
DATABASE_URL=sqlite:///./meeting_minutes.db
```

---

## 10. 依賴清單

```
# 核心
fastapi
uvicorn[standard]
python-multipart
jinja2
sqlalchemy
aiosqlite
pydantic-settings

# AI — 遠端
google-generativeai

# AI — 本地端
openai-whisper

# 音檔處理
pydub

# 工具
python-dotenv
ruff
pytest
httpx                    # 也用於呼叫 Ollama REST API
```

> **注意：** `openai-whisper` 為選裝依賴。若僅使用遠端模式，可不安裝。
> 建議在 `pyproject.toml` 中設為 optional dependency：
> ```toml
> [project.optional-dependencies]
> local = ["openai-whisper"]
> ```

---

## 11. 擴充新 Provider 指南

要新增一個 Provider（例如 Azure Speech + GPT），只需：

1. **建立新檔案** `app/services/providers/azure_provider.py`
2. **實作 `AudioProcessor` 介面**：
   ```python
   class AzureProvider(AudioProcessor):
       async def process(self, file_path: str) -> ProcessingResult:
           ...
       def get_provider_name(self) -> str:
           return "Azure (Remote)"
   ```
3. **更新 `dependencies.py`** 中的工廠函式，新增 `elif` 分支
4. **新增對應的環境變數**

不需要修改 `MeetingProcessor`、API Routes 或前端模板。
