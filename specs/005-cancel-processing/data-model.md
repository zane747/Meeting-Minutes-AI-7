# Data Model: 會議處理中止功能

## Entity Changes

### Meeting (既有表 — 修改)

**變更**: MeetingStatus enum 新增 `CANCELLED` 值

```
MeetingStatus:
  PROCESSING  — 處理中
  COMPLETED   — 已完成
  FAILED      — 失敗
  CANCELLED   — 已取消（新增）
```

**狀態轉換圖**:

```
                    ┌──────────┐
                    │ PROCESSING│
                    └─────┬────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │ COMPLETED│ │  FAILED  │ │CANCELLED │ (新增)
      └──────────┘ └────┬─────┘ └────┬─────┘
                        │            │
                        ▼            ▼
                    ┌──────────┐  ┌──────────┐
                    │PROCESSING│  │PROCESSING│ (重試)
                    └──────────┘  └──────────┘
```

**既有欄位複用**:
- `progress_stage` (VARCHAR 100) — 中止時保留最後的處理階段，用於顯示「已在 X 階段中止」
- `error_message` (TEXT) — 不使用，cancelled 不是錯誤

### 無新增資料表

本功能不需新增任何資料表，僅修改 MeetingStatus enum。
