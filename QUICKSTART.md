# Meeting Minutes AI — 快速啟動指南

> 從零開始把專案跑起來的完整說明。適用於新人接手、換電腦、或過幾週忘了怎麼跑。

---

## 前置需求

| 工具 | 版本 | 用途 | 安裝方式 |
|------|------|------|---------|
| Python | 3.11+ | 程式語言 | https://www.python.org/downloads/ |
| uv | 0.11+ | 套件管理（比 pip 快） | `pip install uv` |
| Git | 任意 | 版本控制 | https://git-scm.com/downloads |
| FFmpeg | 任意 | 音檔處理（pydub 需要） | https://ffmpeg.org/download.html |

**選用（本地模式才需要）：**

| 工具 | 用途 | 安裝方式 |
|------|------|---------|
| Ollama | 本地 LLM 摘要 | https://ollama.ai |
| CUDA Toolkit | GPU 加速 Whisper | https://developer.nvidia.com/cuda-toolkit |

---

## 第一次啟動（5 步）

### Step 1：複製專案

```bash
git clone <你的 repo URL>
cd "Meeting Minutes AI"
```

### Step 2：安裝依賴

```bash
# 基本安裝（遠端模式）
uv sync

# 如果要用本地 Whisper 語音辨識
uv sync --extra local
```

> uv 會自動建立 `.venv/` 虛擬環境，不需要手動建。

### Step 3：設定環境變數

```bash
cp .env.example .env
```

打開 `.env`，**至少**修改這兩個：

```env
# 1. Session 加密密鑰（必改，用下面指令產生）
SESSION_SECRET_KEY=<貼上隨機字串>

# 2. Gemini API Key（用遠端模式才需要）
GEMINI_API_KEY=<你的 Key>
```

產生隨機密鑰：
```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 4：啟動

```bash
uv run uvicorn app.main:app --reload
```

> `--reload` 會在你改程式碼時自動重啟伺服器，開發時必加。

### Step 5：開瀏覽器

```
http://localhost:8000
```

第一次會看到登入頁面 → 點「前往註冊」建立帳號 → 開始使用。

---

## .env 環境變數完整說明

```env
# === AI Provider 切換 ===
MODEL_MODE=remote                # remote（Gemini）/ local（Whisper）

# === Gemini 遠端模式 ===
GEMINI_API_KEY=你的Key           # Google AI Studio 取得
GEMINI_MODEL=gemini-2.0-flash    # 可選 gemini-2.5-pro（更慢但更準）

# === Whisper 本地模式 ===
WHISPER_MODEL=base               # tiny / base / small / medium / large
                                 # 越大越準但越慢，需要越多記憶體

# === Ollama 本地摘要（可選）===
OLLAMA_ENABLED=true              # true 啟用 / false 關閉
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:latest       # 你安裝的 Ollama 模型名稱

# === Session 認證 ===
SESSION_SECRET_KEY=改成隨機字串    # 加密 Cookie 用，每個環境不同

# === 通用 ===
UPLOAD_DIR=./uploads             # 音檔存放路徑
MAX_FILE_SIZE_MB=300             # 上傳檔案大小上限
DATABASE_URL=sqlite+aiosqlite:///./meeting_minutes.db
```

---

## 使用模式對照

| 模式 | 需要網路？ | 需要 GPU？ | 速度 | 品質 | 設定 |
|------|----------|----------|------|------|------|
| **遠端（Gemini）** | 要 | 不用 | 快 | 高 | 只需 API Key |
| **本地（Whisper + Ollama）** | 不用 | 建議有 | 慢 | 中 | 需安裝 Whisper + Ollama |
| **混合（Whisper 轉錄 + 不摘要）** | 不用 | 建議有 | 中 | — | Whisper only，不開 Ollama |

前端上傳頁面可以即時切換模式，不用改 `.env` 重啟。

---

## Ollama 設定（本地摘要）

如果你想在**不連網路**的情況下產生摘要：

```bash
# 1. 安裝 Ollama（https://ollama.ai）

# 2. 下載模型
ollama pull gemma2          # 9B 模型，需要 ~6GB RAM

# 3. 啟動 Ollama 服務
ollama serve

# 4. 在 .env 設定
OLLAMA_ENABLED=true
OLLAMA_MODEL=gemma2:latest
```

---

## 日常指令速查

### 開發

```bash
# 啟動伺服器（自動重載）
uv run uvicorn app.main:app --reload

# 跑全部測試
uv run python -m pytest tests/ -v

# 只跑某個測試檔
uv run python -m pytest tests/test_auth.py -v

# 安裝新套件
uv add <套件名稱>

# 移除套件
uv remove <套件名稱>

# 程式碼格式化 + 檢查
uv run ruff format .
uv run ruff check .
```

### Git

```bash
git status                    # 看改了哪些檔案
git add <檔案>                # 加入暫存區
git commit -m "feat: 描述"    # 提交（用 Conventional Commits 格式）
git log --oneline -10         # 看最近 10 筆提交
```

### 資料庫

```bash
# 重置資料庫（刪掉所有資料，重新建表）
rm meeting_minutes.db
uv run uvicorn app.main:app --reload

# 列出所有使用者
uv run python -c "
import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.database_models import User
async def f():
    async with async_session() as db:
        for u in (await db.execute(select(User))).scalars():
            print(f'  {u.username} (active={u.is_active})')
asyncio.run(f())
"

# 重設使用者密碼
uv run python -c "
import asyncio
from app.database import async_session
from app.services.auth_service import get_user_by_username, hash_password
async def f():
    async with async_session() as db:
        user = await get_user_by_username(db, '帳號')
        if user:
            user.password_hash = hash_password('新密碼')
            await db.commit()
            print('密碼已重設')
asyncio.run(f())
"
```

---

## 專案結構

```
Meeting Minutes AI/
│
├── app/                           ← 所有應用程式碼
│   ├── main.py                    ← 入口：建立 app、掛載 middleware、註冊路由
│   ├── config.py                  ← 環境變數管理（讀 .env）
│   ├── database.py                ← 資料庫引擎和 Session 工廠
│   ├── dependencies.py            ← 依賴注入函式（認證、Provider 選擇）
│   │
│   ├── api/routes/                ← 路由層：URL → 函式
│   │   ├── auth.py                ← 登入/註冊/登出
│   │   ├── pages.py               ← HTML 頁面（首頁、歷史、會議詳情）
│   │   └── meetings.py            ← 會議 REST API（上傳、CRUD、摘要）
│   │
│   ├── models/                    ← 資料模型層
│   │   ├── database_models.py     ← 資料庫表（User, Meeting, ActionItem...）
│   │   └── schemas.py             ← Pydantic 請求/回應驗證
│   │
│   ├── services/                  ← 業務邏輯層
│   │   ├── auth_service.py        ← 密碼雜湊、使用者建立、登入驗證
│   │   ├── audio_service.py       ← 音檔上傳、驗證、儲存
│   │   ├── meeting_processor.py   ← 背景任務：音檔 → AI → 結果存 DB
│   │   ├── annotation_service.py  ← TextGrid/RTTM 標註檔解析
│   │   ├── ollama_service.py      ← 本地 Ollama 摘要
│   │   └── providers/             ← AI Provider（策略模式）
│   │       ├── base.py            ← AudioProcessor 抽象介面
│   │       ├── gemini_provider.py ← Google Gemini 實作
│   │       └── local_whisper_provider.py ← 本地 Whisper 實作
│   │
│   ├── templates/                 ← Jinja2 HTML 模板
│   │   ├── base.html              ← 基礎版型（導覽列、共用 CSS/JS）
│   │   ├── index.html             ← 首頁（上傳表單）
│   │   ├── history.html           ← 歷史紀錄列表
│   │   ├── meeting.html           ← 會議詳情（逐字稿+摘要+Action Items）
│   │   ├── login.html             ← 登入頁
│   │   └── register.html          ← 註冊頁
│   │
│   ├── static/                    ← 靜態資源（目前用 CDN，幾乎空的）
│   └── core/
│       └── exceptions.py          ← 自定義例外
│
├── tests/                         ← pytest 測試
│   ├── conftest.py                ← 共用 fixtures
│   └── test_auth.py               ← 認證功能測試（16 案例）
│
├── specs/                         ← SDD 規格文件（每個功能一個資料夾）
│   └── 006-user-auth/             ← 登入登出功能的完整規格
│       ├── spec.md                ← 需求規格
│       ├── plan.md                ← 技術計畫
│       ├── tasks.md               ← 任務清單
│       ├── research.md            ← 技術決策紀錄
│       ├── data-model.md          ← 資料模型設計
│       ├── quickstart.md          ← 實作導引
│       ├── learning-notes.md      ← 學習筆記
│       ├── contracts/             ← API 合約
│       └── checklists/            ← 需求品質檢查
│
├── uploads/                       ← 上傳的音檔（.gitignore 排除）
├── .env                           ← 環境變數（.gitignore 排除，不進 Git！）
├── .env.example                   ← 環境變數範本
├── pyproject.toml                 ← 專案設定、依賴清單、工具設定
├── uv.lock                        ← 依賴鎖定檔（確保每個人裝到同版本）
├── constitution.md                ← 專案守則（程式碼規範、命名慣例等）
├── meeting_minutes.db             ← SQLite 資料庫（.gitignore 排除）
└── QUICKSTART.md                  ← 本文件
```

---

## 資料流：從上傳到結果

```
使用者在首頁選擇音檔 → 按「上傳並處理」
    ↓
POST /api/meetings/upload-and-process
    ↓
audio_service.validate_audio_file()     驗證格式和大小
    ↓
audio_service.save_file()               存到 uploads/
    ↓
建立 Meeting 記錄（status=PROCESSING）   存入資料庫
    ↓
BackgroundTask: process_meeting()        丟到背景執行
    ↓
provider.process(file_path)             呼叫 AI
    ├── GeminiProvider: 呼叫 Gemini API → 取得逐字稿+摘要+Action Items
    └── LocalWhisperProvider: Whisper 轉錄 → (可選) Ollama 摘要
    ↓
更新 Meeting 記錄（status=COMPLETED）    結果存回資料庫
    ↓
前端 HTMX 每 2 秒輪詢 /api/meetings/{id}/status
    ↓
status=COMPLETED → 頁面跳轉到結果頁
    ↓
使用者看到逐字稿、摘要、Action Items（可編輯）
```

---

## 技術棧

| 層 | 技術 | 用途 |
|----|------|------|
| 後端框架 | FastAPI | 非同步 HTTP 請求處理 |
| 模板引擎 | Jinja2 | 伺服器端渲染 HTML |
| 前端互動 | HTMX 1.9 | 用 HTML 屬性實現 AJAX（不寫 JS） |
| 前端樣式 | Tailwind CSS (CDN) | Utility-first CSS 框架 |
| 資料庫 | SQLite + SQLAlchemy (async) | 輕量級資料儲存 + ORM |
| 認證 | bcrypt + starlette-session | 密碼雜湊 + Session Cookie |
| AI 遠端 | Google Gemini API | 多模態語音辨識 + 摘要 |
| AI 本地 | OpenAI Whisper | 本地語音轉文字 |
| AI 本地摘要 | Ollama (Gemma2) | 本地 LLM 摘要生成 |
| 套件管理 | uv | 快速 Python 套件管理 |
| 測試 | pytest + pytest-asyncio | 自動化測試 |
| 程式碼品質 | ruff | Linting + Formatting |

---

## 常見問題

### 啟動時報錯 `ValidationError: Extra inputs are not permitted`
`.env` 裡有 config.py 沒定義的欄位。確認 `config.py` 的 `model_config` 有 `extra="ignore"`。

### 啟動後看到 FutureWarning: google.generativeai
Google 套件棄用警告，不影響功能。

### 上傳音檔後一直顯示 Processing
- 檢查終端機有沒有錯誤訊息
- 確認 `GEMINI_API_KEY` 正確（遠端模式）
- 確認 FFmpeg 已安裝（`ffmpeg -version`）

### 忘記密碼
v1 沒有密碼重設功能。刪掉 `meeting_minutes.db` 重新註冊，或用上方資料庫指令重設。

### 想換 AI 模型
改 `.env` 的 `MODEL_MODE`、`GEMINI_MODEL` 或 `OLLAMA_MODEL`，重啟伺服器即可。前端上傳頁面也可以即時切換。
