# Quickstart: 會議處理中止功能

## 修改清單（4 個檔案）

### 1. `app/models/database_models.py` — 新增狀態值

```python
class MeetingStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"   # ← 新增
```

### 2. `app/api/routes/meetings.py` — 新增 cancel API + 擴展 retry

新增 `POST /api/meetings/{meeting_id}/cancel` 端點：
- 檢查 meeting 是否存在且 status == PROCESSING
- 將 status 改為 CANCELLED
- 回傳成功訊息

修改 `retry_processing()`：
- 將 `status != FAILED` 放寬為 `status not in (FAILED, CANCELLED)`

### 3. `app/services/meeting_processor.py` — 新增取消檢查點

新增 `_check_cancelled()` 輔助函式：
- 從資料庫重新讀取 meeting status
- 若為 CANCELLED，log 並 return True

在 `process_meeting()` 的每個步驟之間呼叫檢查：
- 健康檢查後
- diarization 後
- AI 轉錄後
- Ollama 摘要前
- 儲存結果前

### 4. `app/templates/meeting.html` — 前端 UI

處理中畫面：
- 新增「中止處理」按鈕（紅色）
- 按下後顯示 confirm() 對話框
- 確認後呼叫 `POST /cancel` API
- 按鈕變灰顯示「中止中...」

已取消畫面（新增 section）：
- 顯示「已取消」狀態
- 顯示中止時的處理階段（從 progress_stage 讀取）
- 提供遠端/本地模式重試按鈕（複用 failed 區塊的按鈕樣式）

輪詢邏輯：
- `htmx:afterRequest` handler 新增 cancelled 狀態判斷
- 偵測到 cancelled → 重新載入頁面

### 5. `app/templates/history.html` — 歷史紀錄標籤

- 新增 cancelled 狀態的標籤樣式（橘色或灰色，與 completed/failed 區分）

## 測試驗證

```
1. 啟動專案
2. 上傳音檔（選 local 模式）
3. 在處理中按「中止處理」
4. 確認：
   - 按鈕變灰 ✓
   - 終端機出現 "Meeting xxx: 偵測到取消" ✓
   - 頁面顯示「已取消」+ 中止階段 ✓
5. 按「重試」→ 確認重新開始處理 ✓
6. 回到歷史紀錄 → 確認狀態標籤正確 ✓
```
