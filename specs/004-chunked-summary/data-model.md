# Data Model: 分段摘要合併

**Feature**: 004-chunked-summary
**Date**: 2026-03-26

## 概述

本功能不新增資料庫表格。所有分段相關的資料結構僅存在於記憶體中（處理過程的中間產物），最終產出的合併摘要沿用現有的 Meeting、ActionItem、Topic 等資料表儲存。

## 記憶體資料結構（非持久化）

### TranscriptChunk

代表從完整逐字稿分割出的一個段落。

| 欄位 | 型別 | 說明 |
|------|------|------|
| index | int | 段落序號（從 0 開始） |
| content | str | 段落文字內容（包含時間戳行） |
| start_time | str | 段落起始時間（MM:SS 格式） |
| end_time | str | 段落結束時間（MM:SS 格式） |
| char_count | int | 段落字數 |

### ChunkSummaryResult

代表單一段落經 LLM 處理後的摘要結果。

| 欄位 | 型別 | 說明 |
|------|------|------|
| chunk_index | int | 對應的段落序號 |
| summary | str | 局部摘要（Markdown） |
| action_items | list[dict] | 局部待辦事項 |
| topics | list[dict] | 局部主題列表（含 start_time / end_time） |
| speaker_summaries | dict | 局部說話者分析（可為空） |
| success | bool | 該段是否成功處理 |
| error_message | str or None | 失敗原因（成功時為 None） |

### MergedSummaryResult

合併所有局部摘要後的最終結果，格式與現有 `generate_summary()` 回傳值一致。

| 欄位 | 型別 | 說明 |
|------|------|------|
| suggested_title | str | 會議標題 |
| summary | str | 完整會議摘要（Markdown） |
| action_items | list[dict] | 去重後的待辦清單 |
| semantic_analysis | dict | 合併後的主題與說話者分析 |
| skipped_chunks | list[dict] | 被跳過的段落資訊（index, start_time, end_time） |
| total_chunks | int | 總段落數 |
| processed_chunks | int | 成功處理的段落數 |

## 既有資料表（不修改）

以下資料表不做結構變更，僅說明與本功能的關係：

- **Meeting**: 儲存合併後的 summary 與 suggested_title（與現有邏輯一致）
- **ActionItem**: 儲存合併去重後的待辦事項
- **Topic**: 儲存合併後的完整主題列表
- **Speaker**: 儲存合併後的說話者分析

## 狀態轉換

分段摘要的處理不新增 MeetingStatus 列舉值。整個分段 → 合併流程視為現有 `processing` 狀態下的子流程。

```
processing (60%) → 分段摘要中（60-78%） → 合併摘要中（78-80%） → 儲存中（80%）
```
