# Data Model: 最新消息 / 公告訊息

## 實體定義

### Announcement（公告）

| 欄位 | 型別 | 約束 | 說明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 唯一識別碼 |
| title | String(255) | NOT NULL | 公告標題 |
| content | Text(5000) | NOT NULL | 公告內容 |
| is_pinned | Boolean | NOT NULL, default=False | 是否置頂 |
| created_by | String(36) | FK → users.id, ON DELETE SET NULL | 發布者 ID |
| created_at | DateTime | NOT NULL, default=utcnow | 建立時間 |
| updated_at | DateTime | NOT NULL, default=utcnow, onupdate=utcnow | 最後更新時間 |

### 關聯

```
Announcement.created_by → User.id (多對一)
  - ON DELETE SET NULL：發布者被刪除時，公告保留但發布者變為 NULL
```

### 索引

- `created_at` DESC：列表頁排序用
- `is_pinned`：快速篩選置頂公告

## 與既有模型的關係

```
User (既有)
  ├── Meeting.created_by (既有)
  └── Announcement.created_by (新增)
```

設計原則與 Meeting 的 `created_by` 完全一致：
- 同樣使用 `ON DELETE SET NULL`
- 同樣透過 `relationship()` 建立 `creator` 關聯
- 同樣的 UUID 主鍵模式
