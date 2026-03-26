# Meeting Minutes AI Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-26

## Active Technologies
- Python 3.11 + FastAPI, httpx, SQLAlchemy (aiosqlite), pydantic-settings, PyTorch (CUDA) (003-ollama-gpu-boost)
- SQLite (aiosqlite) — 不新增資料表 (004-chunked-summary)

- Python 3.11 + FastAPI, OpenAI Whisper, pyannote.audio, PyTorch (CUDA), Ollama (REST API), SQLAlchemy (001-gpu-acceleration)
- SQLite (aiosqlite) (001-gpu-acceleration)

## Project Structure

```text
app/
├── api/routes/
├── config.py
├── database.py
├── main.py
├── models/
├── services/
│   ├── providers/
│   ├── device_manager.py
│   ├── diarization_service.py
│   └── ollama_service.py
├── static/
└── templates/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python: Follow standard conventions

## Recent Changes
- 004-chunked-summary: Added Python 3.11 + FastAPI, httpx, SQLAlchemy (aiosqlite), pydantic-settings, PyTorch (CUDA)
- 003-ollama-gpu-boost: Added Python 3.11 + FastAPI, httpx, SQLAlchemy (aiosqlite), pydantic-settings, PyTorch (CUDA)

- 002-gpu-cpu-workload-split: GPU/CPU workload split — Whisper+Diarization on GPU, Ollama defaults to CPU (configurable via OLLAMA_GPU)

<!-- MANUAL ADDITIONS START -->

## Language

所有回應、生成的文件與註解請使用繁體中文。程式碼中的變數名稱、函式名稱維持英文。

<!-- MANUAL ADDITIONS END -->
