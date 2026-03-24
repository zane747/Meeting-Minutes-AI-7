# 需求澄清（Clarification）

> 對照 `spec.md`、`plan.md` 與 `constitution.md`，記錄所有已確認的決策。

---

## 第一輪澄清（2026-03-24 已確認）

<details>
<summary>點擊展開已確認的決策（Q1-Q10）</summary>

| # | 問題 | 決策 |
|---|------|------|
| Q1+Q2 | AI 模型與處理流程 | 全面改用 Gemini API + 一鍵處理 → 後續升級為策略模式雙軌架構 |
| Q3 | 時間戳記格式 | 段落式 |
| Q4 | 會議標題來源 | 選填 + AI 自動生成 |
| Q5 | 歷史紀錄功能 | 時間倒序 + 刪除，無搜尋分頁 |
| Q6 | 摘要輸出語言 | 統一繁體中文 |
| Q7 | 編輯範圍 | Markdown 純文字 + Action Items 增刪改 |
| Q8 | 錯誤重試 | 手動重新觸發 |
| Q9 | 並行處理 | MVP 不允許並行 |
| Q10 | 資料保留 | 文字永久保留，音檔可手動刪除 |

</details>

---

## 第二輪澄清（2026-03-24 已確認）

### Q11：本地模式缺摘要時的 UX 處理

**決策：** ✅ **摘要設為可選觸發 + 條件隱藏**

- LocalWhisperProvider 計畫串接 Ollama 提供本地摘要功能
- 若使用者已配置 Ollama → 摘要功能正常可用
- 若使用者未配置 Ollama → 隱藏摘要區塊，顯示「配置 Ollama 以啟用本地摘要」提示

---

### Q12：Provider 不可用時的處理

**決策：** ✅ **兩者兼具**

- **啟動時：** 偵測 `.env` 配置與模型連通性，不可用時 warning log
- **執行時：** 任務前再次確認 Provider 可用，失聯則報錯給使用者

---

### Q13：重試時能否切換 Provider

**決策：** ✅ **允許切換**

- 重試 API 接受 `?mode=` 參數
- 典型場景：Gemini 429 限制 → 使用者改選本地端 Provider 重試
- 更新 Meeting 的 `provider` 欄位

---

### Q14：Whisper 模型載入策略

**決策：** ✅ **延遲載入 + 快取（Lazy Load with Caching）**

- 第一次呼叫時載入模型至記憶體
- 之後保持駐留，直到程式關閉
- 避免每次處理都重新載入的延遲

---

### Q15：本地端逐字稿語言輸出

**決策：** ✅ **保留原始語言**

- 本地端轉錄保留音檔的原始語言輸出
- 不強制轉為繁體中文
- 未來串接 LLM 時再處理翻譯

---

### Q16：音檔時長取得方式

**決策：** ✅ **上傳時計算**

- 前端透過瀏覽器 API 取得時長，顯示在列表中
- 後端也透過 `pydub` 計算作為備用驗證

---

### Q17：刪除確認機制

**決策：** ✅ **瀏覽器內建 confirm 對話框**

- 簡單的 `confirm("確定要刪除？")` 即可
- 不需要自定義 modal

---

### Q18：上傳與處理的流程

**決策：** ✅ **一步驟**

- 使用者選擇音檔 → 按下「開始」 → 系統自動完成上傳 + 處理
- 合併為單一操作，符合「簡單有力」原則
- API 層面：`POST /api/meetings/upload` 成功後自動觸發 `process`

---

### Q19：Gemini 429 rate limit 處理

**決策：** ✅ **區分錯誤類型**

- **429 Rate Limit：** 提示「API 頻率受限，請稍候或切換本地模式」
- **401 API Key 無效：** 提示「API Key 設定錯誤，請檢查 .env 設定」
- **其他錯誤：** 通用錯誤提示 + 重試按鈕

---

## 第三輪澄清（2026-03-24 已確認 — TextGrid / RTTM / FLAC 新功能）

### Q20：AudioProcessor.process() 介面變更

**決策：** ✅ **新增可選 `ProcessingContext` 參數**

- `process(file_path, context=None)` — `context` 預設 `None`，既有 Provider 不受影響
- `ProcessingContext` dataclass 攜帶 TextGrid 逐字稿與 RTTM 說話者資訊
- Provider 收到 context 後可決定是否跳過轉錄、注入角色資訊至 Prompt

---

### Q21：TextGrid/RTTM 解析應在哪一層？

**決策：** ✅ **C — 獨立 Service**

- 新建 `app/services/annotation_service.py`
- 職責分離：`parse_textgrid()` 與 `parse_rttm()` 各自獨立
- 解析結果由 `MeetingProcessor` 協調，組裝為 `ProcessingContext` 傳入 Provider

---

### Q22：有 TextGrid 時的處理流程

**決策：** ✅ **C — 使用者可選擇**

- 上傳頁提供選項：「使用 TextGrid 逐字稿」或「重新 AI 轉錄」
- 選「使用 TextGrid」→ 跳過 Provider 轉錄，僅做摘要
- 選「重新 AI 轉錄」→ 忽略 TextGrid 逐字稿，照常呼叫 Provider

---

### Q23：RTTM 角色標籤如何與 AI 轉錄結合

**決策：** ✅ **B — 前處理注入 Prompt**

- 將 RTTM 說話者片段資訊注入 Gemini Prompt，讓 AI 直接產出帶角色標籤的逐字稿
- 本地模式（Whisper）：轉錄後再根據 RTTM 時間軸後處理合併

---

### Q24：DB Meeting 模型新增欄位

**決策：** ✅ **獨立 `AnnotationFile` 關聯表**

- 新建 `annotation_files` 資料表，與 Meeting 一對多關聯
- 欄位：id, meeting_id, file_type (textgrid/rttm), file_name, file_path, parsed_data (JSON)
- 不在 Meeting 表中新增欄位，保持主表乾淨

---

### Q25：API 多檔案上傳

**決策：** ✅ **A — 多個 UploadFile 參數**

- `file: UploadFile`（音檔，必要）
- `textgrid: UploadFile | None = None`（TextGrid，選填）
- `rttm: UploadFile | None = None`（RTTM，選填）
- 後端依參數名稱區分，不依賴副檔名判斷
