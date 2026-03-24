# Meeting Minutes AI

AI 驅動的會議紀錄應用程式，支援語音辨識、自動摘要與結構化輸出。

## 功能

- **音檔上傳**：支援 .mp3 / .wav / .flac，300MB 上限
- **一鍵 AI 處理**：自動產出逐字稿、會議摘要、Action Items
- **雙軌 Provider**：
  - **遠端模式**：Gemini API（一次產出全部結果）
  - **本地模式**：Whisper 轉錄 + Ollama 摘要（可選）
- **結果編輯**：Markdown 純文字編輯逐字稿與摘要
- **歷史紀錄**：瀏覽與管理過去的會議紀錄

## 快速開始

### 1. 安裝依賴

```bash
uv sync
```

若需本地端 Whisper：

```bash
uv sync --extra local
```

### 2. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`，至少設定：

```env
GEMINI_API_KEY=your-gemini-api-key
```

### 3. 啟動

```bash
uv run uvicorn app.main:app --reload
```

開啟瀏覽器前往 http://localhost:8000

## Provider 切換

透過 `.env` 中的 `MODEL_MODE` 設定預設 Provider：

| 值 | 說明 |
|----|------|
| `remote` | 使用 Gemini API（預設） |
| `local` | 使用本地 Whisper + Ollama |

前端介面也可在上傳時即時切換。

## Ollama 配置（本地摘要）

1. 安裝 Ollama：https://ollama.ai
2. 拉取模型：`ollama pull gemma2:9b`
3. 在 `.env` 中設定：

```env
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:9b
```

## 技術棧

- **後端**：Python 3.11+ / FastAPI / SQLAlchemy / SQLite
- **前端**：Jinja2 + HTMX + Tailwind CSS
- **AI**：Gemini API / OpenAI Whisper / Ollama (Gemma 2 9B)
