# Quickstart: 分段摘要合併

**Feature**: 004-chunked-summary
**Date**: 2026-03-26

## 前置條件

- Python 3.11+
- Ollama 已安裝且運行中（`ollama serve`）
- gemma2 模型已下載（`ollama pull gemma2`）
- RTX 4050 或同等級 GPU（6GB+ VRAM）

## 環境設定

在 `.env` 中確認以下設定：

```env
OLLAMA_ENABLED=true
OLLAMA_MODEL=gemma2
OLLAMA_NUM_CTX=32768
OLLAMA_GPU=auto
```

注意：`OLLAMA_NUM_CTX` 建議設為 32768 以支援合併摘要步驟。

## 測試驗證

### 驗證短會議（不分段）

1. 上傳一段 5 分鐘的會議錄音
2. 確認系統以單次模式完成摘要
3. 確認摘要格式正常

### 驗證長會議（分段模式）

1. 上傳一段 40 分鐘以上、包含多個議題的會議錄音
2. 觀察前端進度顯示（應出現「第 X/Y 段」）
3. 確認最終摘要涵蓋所有議題
4. 確認待辦事項清單完整且無重複
5. 確認主題時段分析涵蓋整場會議

### 驗證失敗容錯

1. 在 Ollama 處理中途暫停 Ollama 服務模擬失敗
2. 確認系統產出部分摘要並標註遺漏時段
3. 確認未崩潰，狀態正確更新

## 關鍵檔案

| 檔案 | 說明 |
|------|------|
| `app/services/ollama_service.py` | 分段邏輯、分段摘要與合併摘要的核心實作 |
| `app/services/meeting_processor.py` | 整合分段流程並回報進度 |
| `app/config.py` | `OLLAMA_NUM_CTX` 設定 |
