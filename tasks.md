# 任務清單（Tasks）— 說話者辨識與語意分析

> 根據 Specify → Plan → Analyze 交叉一致性檢查後的修正版本。
> 所有 Analyze 修正建議皆已整合，修正點以 `★` 標記。

---

## Phase 0：GPU 加速（VRAM 動態分配）

> 前置條件：使用者需自行安裝 PyTorch CUDA 版。
> 硬體：RTX 4050 Laptop（6 GB VRAM），Ollama 常駐佔 ~5.3 GB。
> 策略：循序處理流程中輪流使用 GPU，每階段用完釋放。

---

### Task 0.1 — 設定與 DeviceManager 基礎

- [ ] `app/config.py` 新增設定項：
  - `DEVICE: str = "auto"`（`"auto"` | `"cpu"` | `"cuda"`）
- [ ] `app/config.py` 修改 Whisper 預設模型：
  - `WHISPER_MODEL: str = "medium"`（從 `"base"` 升級）
- [ ] `.env.example` 新增 `DEVICE=auto` 與說明
- [ ] 新增 `app/services/device_manager.py`：
  - `get_device() → str`：根據設定 + CUDA 可用性回傳 `"cuda"` 或 `"cpu"`
  - `release_gpu_memory()`：呼叫 `torch.cuda.empty_cache()` + `gc.collect()`
  - `mark_cpu_fallback()`：OOM 後標記 `_force_cpu = True`，**僅影響下次請求**，本次請求後續步驟仍嘗試 GPU（★修正 #3）
  - `reset_fallback()`：重置標記（app 重啟時自動重置）
  - ★ 啟動時 log 顯示偵測結果：使用 `torch.cuda.get_device_name()` + `torch.cuda.get_device_properties().total_mem` 取得 GPU 名稱與 VRAM 大小（★修正 #2）
- [ ] `torch` 為 optional import：未安裝時 `get_device()` 恆回傳 `"cpu"`
- [ ] ★ PyTorch CPU 版偵測（★修正 #5）：若 `torch` 已安裝但 `cuda.is_available() == False`，額外 log warning：
  `WARNING: PyTorch installed but CUDA not available. To enable GPU: pip install torch --index-url https://download.pytorch.org/whl/cu121`

**驗證：**
- 有 CUDA → log 顯示 `Using device: cuda (NVIDIA GeForce RTX 4050 Laptop GPU, 6.0 GB)`
- 無 CUDA / 無 torch → log 顯示 `Using device: cpu`
- PyTorch CPU 版 → log 顯示 warning 提示安裝 CUDA 版
- `DEVICE=cpu` → 即使有 CUDA 也回傳 `"cpu"`

---

### Task 0.2 — Ollama Unload/Reload 機制

- [ ] `app/services/device_manager.py` 新增：
  - `unload_ollama()`：釋放 Ollama 佔用的 VRAM
  - ★ 先呼叫 `GET /api/ps` 取得**實際載入中的模型名稱**，不依賴 `settings.OLLAMA_MODEL`（★修正 #1）
  - 若 `/api/ps` 回傳無模型 → 跳過 unload
  - 對每個載入中的模型：POST `/api/generate` `{"model": "<name>", "keep_alive": 0}`
  - unload 失敗 → log warning，不中斷流程（fallback 到 CPU 跑 Whisper/pyannote）
- [ ] Ollama reload 不需手動處理 — 下次呼叫 `/api/chat` 時自動 reload

**驗證：**
- 呼叫 unload → `ollama ps` 顯示無模型 → 呼叫 generate → 自動 reload
- Ollama 未啟動 → unload 靜默失敗，不影響流程
- config 模型名與實際載入模型不同 → 仍能正確 unload

---

### Task 0.3 — Whisper GPU 加速

- [ ] `app/services/providers/local_whisper_provider.py` 修改：
  - `_load_model()` 加入 `device` 參數：`whisper.load_model(size, device=device)`
  - 移除 class-level cache（`_model` 和 `_cached_model_size`）
  - 改為 instance 變數，每次 transcribe 後設為 `None`
  - `finally` 區塊呼叫 `DeviceManager.release_gpu_memory()`
- [ ] OOM 處理：
  - `except torch.cuda.OutOfMemoryError` → `DeviceManager.mark_cpu_fallback()`
  - ★ `mark_cpu_fallback` 僅標記下次請求走 CPU，本次請求失敗並回傳錯誤訊息（★修正 #3）
  - 錯誤訊息提示「VRAM 不足，已切換為 CPU 模式，請重新提交」
  - 下次請求自動走 CPU

**驗證：**
- GPU 可用 → Whisper 在 GPU 上跑，完成後 `nvidia-smi` 顯示 VRAM 已釋放
- GPU 不可用 → 靜默 fallback CPU，行為與現在完全一致
- OOM → 錯誤訊息 + 下次自動 CPU

---

### Task 0.4 — pyannote GPU 加速（★修正 #4：合併至 Task 1.3）

> ★ 此 Task 不再獨立修改 `diarization_service.py`。
> GPU 支援直接整合到 Phase 1 Task 1.3（DiarizationService 新建）中。
> Task 1.3 建檔時直接以 Phase 0 規格實作：無 class-level cache、有 GPU 支援。

- [ ] 確認 Task 1.3 包含以下 GPU 相關要求：
  - `_load_pipeline()` 加入 `pipeline.to(torch.device(device))`
  - 不使用 class-level cache，每次 diarize 後釋放 pipeline
  - `finally` 區塊呼叫 `DeviceManager.release_gpu_memory()`
  - OOM 處理：不中斷流程（Graceful Degradation），設定 `diarization_warning`
  - ★ `mark_cpu_fallback` 僅標記下次請求走 CPU，本次 pyannote OOM 後 Whisper 仍嘗試 GPU（★修正 #3）

**驗證：**
- GPU 可用 → pyannote 在 GPU 上跑，完成後 VRAM 釋放
- OOM → diarization 跳過，warning 傳到前端，**Whisper 仍嘗試 GPU**（因 pyannote 已釋放 VRAM）
- 下次請求 → 自動走 CPU

---

### Task 0.5 — meeting_processor 流程協調

- [ ] `app/services/meeting_processor.py` 修改 `process_meeting()`：
  - Step 0：若 `device == "cuda"` 且 `OLLAMA_ENABLED` → `await DeviceManager.unload_ollama()`
  - Step 1：Diarization（GPU → 內部釋放）
  - Step 2：Transcription（GPU → 內部釋放）
  - Step 3：Ollama summary（自動 reload，不需手動處理）
- [ ] 若 Step 0 unload 失敗 → 不中斷，Whisper/pyannote 可能 OOM 但有 fallback
- [ ] Log 每個階段的 device 使用情況

**驗證：**
- 完整流程：unload Ollama → pyannote(GPU) → 釋放 → Whisper(GPU) → 釋放 → Ollama(自動reload) → 摘要
- 無 GPU：流程與現在完全一致，多一行 log `Skipping Ollama unload (CPU mode)`

---

### Phase 0 依賴圖

```
0.1 ──→ 0.2（DeviceManager 基礎 → Ollama unload）
0.1 ──→ 0.3（DeviceManager 基礎 → Whisper GPU）
0.1 ──→ 0.4（★ 合併至 Task 1.3，僅作為檢查清單）
0.2 + 0.3 ──→ 0.5（整合到 pipeline）
Task 1.3（含 GPU）──→ 0.5
```

### Phase 0 → Phase 1 影響

- ★ Task 1.3（DiarizationService）：直接以 Phase 0 規格建檔 — 無 class-level cache、含 GPU 支援（★修正 #4）
- Task 1.1（依賴）：`torch` 已在 `diarization` extra group，無需額外變更
- 其餘 Phase 1-3 任務不受影響

### Analyze 修正對照表（Phase 0）

| # | 問題 | 嚴重度 | 修正位置 |
|---|------|--------|---------|
| #1 | Ollama unload 模型名稱不一致 | 中 | Task 0.2 — 改用 `GET /api/ps` 動態取得 |
| #2 | 缺 VRAM 查詢方法 | 低 | Task 0.1 — 補充 `get_device_name()` + `get_device_properties()` |
| #3 | OOM fallback 作用域 | 中 | Task 0.1, 0.3, 0.4/1.3 — `mark_cpu_fallback` 僅影響下次請求 |
| #4 | Phase 0 Task 0.4 與 Phase 1 Task 1.3 重疊 | 中 | Task 0.4 合併至 Task 1.3，建檔時直接含 GPU 支援 |
| #5 | PyTorch CPU 版無提示 | 低 | Task 0.1 — 偵測時加 warning log |

---

## Phase 1：pyannote Diarization 核心整合

### Task 1.1 — 依賴與設定

- [ ] `pyproject.toml` ★ 新增獨立 extra group `diarization`：`pyannote.audio`、`torch`
  - 不放在 `local` group，因為 remote 模式也可能使用 diarization（★修正 #1.2）
  - `local` group 維持只有 `openai-whisper`
- [ ] `app/config.py` 新增設定項：
  - `DIARIZATION_ENABLED: bool = False`（全域預設關閉）
  - `HF_TOKEN: str = ""`（HuggingFace access token）
  - `DIARIZATION_DEFAULT_NUM_SPEAKERS: int = 0`（0 = 自動偵測）
- [ ] `.env.example` 補上對應環境變數範例與說明

**驗證：** `uv sync --extra diarization` 能成功安裝 pyannote

---

### Task 1.2 — DB Schema 擴充（speakers + utterances）

- [ ] `app/models/database_models.py` 新增 `Speaker` model：
  - `id`（UUID, PK）
  - `meeting_id`（FK → meetings, CASCADE DELETE）
  - `label`（String, NOT NULL）— "Speaker_0"
  - `display_name`（String, nullable）— 使用者自訂名稱
  - `color`（String, nullable）— UI 顏色 "#FF6B6B"
- [ ] `app/models/database_models.py` 新增 `Utterance` model：
  - `id`（UUID, PK）
  - `meeting_id`（FK → meetings, CASCADE DELETE）
  - `speaker_id`（FK → speakers, SET NULL）
  - `start_time`（Float, NOT NULL）— 秒數
  - `end_time`（Float, NOT NULL）
  - `text`（Text, NOT NULL）
  - `intent_tag`（String, nullable）— Phase 3 才填入
  - `order_index`（Integer, NOT NULL）— 排序用
- [ ] `Meeting` model 新增 `relationship` 到 `speakers` 和 `utterances`（cascade delete）
- [ ] `app/models/schemas.py` 新增 response schema：
  - `SpeakerResponse`（id, label, display_name, color）
  - `UtteranceResponse`（id, speaker_label, speaker_display_name, start_time, end_time, text, intent_tag）

**驗證：** 啟動 app 後 SQLite 自動建立新表，無報錯；舊的 meeting 資料不受影響

---

### Task 1.2.1 — DB Migration 策略（★修正 #2.1 新增）

- [ ] 評估現有 DB 狀態：目前使用 `metadata.create_all()` 自動建表
- [ ] Phase 1-2 皆為新增表，`create_all()` 可正常處理，暫不需 migration
- [ ] 為 Phase 3 預備（Speaker 新增 `key_points` 欄位需 ALTER TABLE）：
  - 引入 Alembic：`alembic init alembic`
  - 設定 `alembic.ini` 連接現有 SQLite
  - 產生 initial migration（基於現有 schema snapshot）
- [ ] 在 Phase 3 開始前完成 Alembic 設定

**驗證：** `alembic upgrade head` 能在有既有資料的 DB 上正確執行

---

### Task 1.3 — DiarizationService 實作（★含 Phase 0 GPU 支援）

- [ ] 新增 `app/services/diarization_service.py`
- [ ] 實作 `is_available() → bool`：
  - 檢查 `pyannote.audio` 是否已安裝（`try import`）
  - 檢查 `HF_TOKEN` 是否已設定
  - 任一不滿足回傳 False
- [ ] 實作 `diarize(file_path, num_speakers=None) → List[SpeakerSegment]`：
  - ★ 不使用 class-level cache（Phase 0 規格），每次呼叫載入 Pipeline，完成後釋放（★修正 Phase 0 #4）
  - ★ `_load_pipeline()` 使用 `DeviceManager.get_device()` 取得 device，`pipeline.to(torch.device(device))`
  - ★ `finally` 區塊：pipeline 設為 `None`，呼叫 `DeviceManager.release_gpu_memory()`
  - `num_speakers=None` → 自動偵測；`num_speakers=N` → 指定人數
  - 回傳格式：`[{speaker: "Speaker_0", start: 0.0, end: 5.2}, ...]`
- [ ] 實作 `merge_with_transcript(segments, transcript_lines) → List[UtteranceInfo]`：
  - 將 diarization 時間段與逐字稿文字按時間戳對齊
  - 每段文字配對到最接近的 speaker segment
- [ ] ★ Graceful Degradation 錯誤處理（★修正 #2.2 + Phase 0 #3）：
  - pyannote 未安裝 → log warning，回傳空 list，繼續處理
  - HF_TOKEN 無效 → 同上
  - ★ CUDA OOM → `DeviceManager.mark_cpu_fallback()`（僅影響下次請求），回傳空 list，設定 warning，本次後續步驟（Whisper）仍嘗試 GPU
  - 其他執行失敗 → catch exception，log error，回傳空 list
  - 任何 diarization 失敗都不應導致整個會議處理失敗
  - 在處理結果中標記 `diarization_warning: str`，傳遞到前端顯示

**驗證：**
- 正常：傳入測試音檔 → 回傳正確 speaker segments
- GPU：pyannote 在 GPU 上跑，完成後 VRAM 釋放
- OOM：diarization 跳過，warning 傳到前端，Whisper 仍嘗試 GPU
- 異常：不設 HF_TOKEN → 會議仍正常處理，無 speaker，UI 顯示警告

---

### Task 1.4 — ProcessingContext / ProcessingResult 擴充

- [ ] `app/services/providers/base.py` — `ProcessingContext` 新增：
  - `diarization_enabled: bool = False`
  - `num_speakers: int | None = None`
- [ ] `app/services/providers/base.py` — `ProcessingResult` 新增：
  - `speakers: list[dict] = field(default_factory=list)`
  - `utterances: list[dict] = field(default_factory=list)`
  - `diarization_warning: str | None = None`

**驗證：** 現有 provider 仍能正常運作（新欄位皆有預設值）

---

### Task 1.5 — Pipeline 整合（meeting_processor）

- [ ] `app/services/meeting_processor.py` — 在 `process_meeting()` 中插入 diarization 步驟
- [ ] ★ RTTM 優先判斷（★修正 #1.1）：
  ```
  if diarization_enabled:
      if context.speakers 已有值（來自 RTTM）:
          → 跳過 pyannote，使用 RTTM
      elif diarization_service.is_available():
          → 執行 pyannote diarize
      else:
          → 設定 diarization_warning
  ```
- [ ] 處理完成後的 DB 寫入：
  - 從 transcript + diarization segments 組合 speakers 與 utterances
  - 自動分配顏色（8-10 色預設調色盤循環）
  - 寫入 `speakers` 表和 `utterances` 表
- [ ] `meeting.transcript` 欄位保留完整純文字（向下相容）

**驗證：**
- 音檔 + diarization → speakers/utterances 表有資料
- 音檔 + RTTM + diarization → 使用 RTTM，不跑 pyannote
- 音檔 + 不啟用 diarization → 與現有行為完全相同

---

### Task 1.6 — 上傳 API 擴充

- [ ] `app/api/routes/meetings.py` — `upload-and-process` 端點新增 Form 參數：
  - `enable_diarization: bool = False`
  - `num_speakers: int | None = None`
- [ ] ★ `app/models/schemas.py` 同步新增 request schema（★修正 #2.4）
- [ ] 將參數傳入 ProcessingContext → 傳遞到 meeting_processor

**驗證：** POST 帶 `enable_diarization=true&num_speakers=3` 正確傳遞到 pipeline

---

## Phase 2：說話者 UI 功能

### Task 2.1 — 上傳頁面 UI

- [ ] `app/templates/index.html` — 新增可收合區塊：
  - ☐ 啟用說話者辨識
  - 展開後：○ 自動偵測人數 / ○ 指定人數 [___] 人
- [ ] 預設收合，勾選後展開
- [ ] JS：將 `enable_diarization` 和 `num_speakers` 加入 form submission
- [ ] 根據 `DIARIZATION_ENABLED` 決定 checkbox 預設狀態
- [ ] ★ 不做事前預填名稱，延後到 Task 2.5.1（★修正 #1.3）

**驗證：** 勾選 → API 收到參數；不勾選 → 與現有行為相同

---

### Task 2.2 — 說話者管理 API

- [ ] `GET /api/meetings/{meeting_id}/speakers` — 回傳 speakers 列表
- [ ] `PUT /api/meetings/{meeting_id}/speakers/{speaker_id}` — 更新 display_name / color
- [ ] ★ 不自動替換 `meeting.transcript`（★修正 #2.3）：
  - 名稱只在 `speakers` 表生效
  - UI 閱讀模式從 `utterances` 表動態組合（帶 display_name）
  - UI 編輯模式顯示原始 `meeting.transcript`

**驗證：** 改名 → speakers API 回傳新名稱 → 閱讀模式顯示新名稱 → transcript 不變

---

### Task 2.3 — 發言篩選 API

- [ ] `GET /api/meetings/{meeting_id}/utterances` — 回傳所有結構化發言
  - Query param：`?speaker_id=xxx`（篩選特定說話者）
  - 回傳包含 speaker 的 display_name 和 color
  - `key_points` 暫回傳 null（Phase 3 填入）

**驗證：** 帶 speaker_id → 正確篩選；不帶 → 回傳全部

---

### Task 2.4 — 會議詳情頁 UI（說話者區塊）

- [ ] `app/templates/meeting.html` — 新增說話者列表區塊
- [ ] ★ 無 diarization 資料時完全隱藏，不影響現有 UI（★修正 #3.1）
- [ ] 每個說話者：顏色圓點 + label/display_name + 編輯按鈕 + 篩選按鈕
- [ ] HTMX 互動：
  - 編輯：`hx-put` inline 更新
  - 篩選：`hx-get` 局部替換
  - 顯示全部：恢復完整逐字稿
- [ ] 若有 `diarization_warning` → 黃色警告 banner
- [ ] 新增閱讀模式 / 編輯模式切換：
  - 閱讀模式：從 utterances 動態渲染，帶名稱和顏色
  - 編輯模式：原始 transcript textarea（現有行為）

**驗證：**
- 有 speakers → 列表 + 篩選正常
- 無 speakers → 與現有頁面完全一致
- 閱讀/編輯切換正常

---

### Task 2.5 — 逐字稿 Speaker 標籤上色（閱讀模式）

- [ ] 閱讀模式下，每段發言以對應 speaker 顏色高亮標籤
- [ ] 點擊 speaker 標籤 → 觸發篩選
- [ ] 預設調色盤（8-10 色循環）

**驗證：** 不同說話者不同顏色；點擊標籤觸發篩選

---

### Task 2.5.1 — 事前預填說話者名稱（★修正 #1.3 延後功能）

- [ ] `app/templates/index.html` — 啟用 diarization 後可選展開「預填說話者名稱」
  - 動態新增/刪除名稱欄位
  - 名稱按順序對應 Speaker_0, Speaker_1...
- [ ] API 新增 `preset_speaker_names: str | None`（JSON string）
- [ ] 處理完成後寫入 `speakers.display_name`
- [ ] 預填人數 ≠ 偵測人數 → 多餘忽略，不足保持空白

**驗證：** 預填 3 名 → 偵測 3 人 → 正確對應；偵測 5 人 → 前 3 有名，後 2 空白

---

## Phase 3：語意分析

### Task 3.1 — Prompt 擴充（Gemini）

> ★ 依賴 Task 2.3（utterances API 穩定後）（★修正 #3.2）

- [ ] `gemini_provider.py` — prompt JSON output 新增 `semantic_analysis`：
  - `topics`：主題分段（title, start_time, end_time, speakers_involved）
  - `speaker_summaries`：每人訴求歸納（key_points, stance, action_suggestions）
  - `utterance_intents`：每段發言意圖（utterance_index, intent）
- [ ] ★ 無 diarization 時的 prompt variant（★修正 #3.1）：
  - 不產 `speaker_summaries`
  - `topics` 不含 `speakers_involved`
  - `utterance_intents` 仍正常產出
- [ ] 指示 AI 自行決定 intent 標籤和主題粒度（不設固定集合）

**驗證：** Gemini 回傳含正確格式的 semantic_analysis

---

### Task 3.2 — Prompt 擴充（Ollama）

- [ ] `ollama_service.py` — 擴充 prompt，格式與 Gemini 一致
- [ ] 考慮本地模型能力，可簡化（只產 topics + speaker_summaries）

**驗證：** Ollama 回傳含 semantic_analysis（至少 topics）

---

### Task 3.3 — DB Schema 擴充（topics + speaker key_points）

> 前置：Task 1.2.1（Alembic 已就緒）

- [ ] 新增 `Topic` model（id, meeting_id, title, start_time, end_time, order_index）
- [ ] `Speaker` model 新增欄位（透過 Alembic migration）：
  - `key_points`（Text, nullable）
  - `stance`（String, nullable）
- [ ] `meeting_processor.py` — 解析 semantic_analysis → 寫入 topics、speakers、utterances
- [ ] `schemas.py` 新增 `TopicResponse`

**驗證：** 處理完後 topics 表有資料、speakers.key_points 有值、utterances.intent_tag 有值

---

### Task 3.4 — 主題目錄 UI

- [ ] `meeting.html` — 主題目錄區塊（TOC 風格）
  - 每主題：標題 + 時間範圍
  - ★ 有 diarization → 額外顯示參與說話者；無 → 只顯示主題（★修正 #3.1）
- [ ] 點擊主題 → 捲動到對應逐字稿段落
- [ ] `GET /api/meetings/{meeting_id}/topics` — 新增端點

**驗證：** 主題目錄正確；點擊跳轉；無 diarization 時不顯示說話者

---

### Task 3.5 — 意圖標籤 UI

- [ ] 閱讀模式每段發言旁顯示意圖 badge（半透明色）
- [ ] 意圖篩選 dropdown（從實際資料收集可用標籤）

**驗證：** 標籤正確顯示；篩選正常

---

### Task 3.6 — 說話者訴求摘要 UI

- [ ] 篩選說話者時，頂部顯示 key_points + stance 摘要卡片
- [ ] 說話者列表中可預覽簡短摘要
- [ ] ★ 僅在有 diarization + speaker_summaries 資料時顯示（★修正 #3.1）

**驗證：** 訴求摘要與該說話者實際發言吻合

---

## 修正後的依賴圖

```
Phase 1（基礎設施）:
  1.1 ──→ 1.3 ──→ 1.5 ──→ 1.6
  1.1 ──→ 1.2 ──↗      ↗
  1.1 ──→ 1.2.1（Alembic，可平行）
          1.4 ───┘

Phase 2（說話者 UI）:
  1.6 ──→ 2.1
  1.2 ──→ 2.2 ──→ 2.4 ──→ 2.5
  1.2 ──→ 2.3 ──↗
  2.1 ──→ 2.5.1（延後功能）

Phase 3（語意分析）:        ★ 修正：3.1 依賴 2.3
  2.3 ──→ 3.1
  2.3 ──→ 3.2
  1.2.1 → 3.3（依賴 Alembic）
  3.1 ──→ 3.3 ──→ 3.4
               ──→ 3.5
  2.4 ──→ 3.6
```

---

## Analyze 修正對照表

| # | 問題 | 嚴重度 | 修正位置 |
|---|------|--------|---------|
| 1.1 | RTTM vs pyannote 衝突 | 中 | Task 1.5 — RTTM 優先判斷 |
| 1.2 | pyannote 依賴分組 | 中 | Task 1.1 — 獨立 `diarization` extra group |
| 1.3 | 預填名稱配對邏輯 | 低 | Task 2.5.1 — 延後到 Phase 2 |
| 2.1 | 缺 Migration 任務 | 高 | Task 1.2.1 — 新增 Alembic 任務 |
| 2.2 | 缺錯誤處理 / fallback | 高 | Task 1.3 — Graceful Degradation |
| 2.3 | transcript 字串替換風險 | 中 | Task 2.2 — utterances 動態組合 |
| 2.4 | Request schema 遺漏 | 低 | Task 1.6 — 明確標註 |
| 3.1 | 無 speaker 的 UI 狀態 | 中 | Task 2.4, 3.4, 3.6 — 條件渲染 |
| 3.2 | 依賴圖錯誤 | 低 | 依賴圖 — 3.1 依賴 2.3 |
