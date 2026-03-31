# API Contracts: 公告訊息

## POST /api/announcements

建立公告（Role 1, 2）

**Request:**
```json
{
  "title": "系統維護通知",
  "content": "本系統將於 2026-04-05 進行維護..."
}
```

**Response 200:**
```json
{
  "id": "uuid",
  "title": "系統維護通知",
  "content": "本系統將於 2026-04-05 進行維護...",
  "is_pinned": false,
  "created_by": "user-uuid",
  "created_at": "2026-03-31T12:00:00",
  "updated_at": "2026-03-31T12:00:00"
}
```

**Error 403:** `{"detail": "權限不足"}`

## PUT /api/announcements/{id}

編輯公告（發布者或 Role 1）

**Request:**
```json
{
  "title": "更新後的標題",
  "content": "更新後的內容"
}
```

**Response 200:** 同建立回應格式

**Error 403:** `{"detail": "僅發布者或超級管理員可編輯"}`
**Error 404:** `{"detail": "公告不存在"}`

## DELETE /api/announcements/{id}

刪除公告（發布者或 Role 1）

**Response 200:** `{"detail": "公告已刪除"}`

**Error 403:** `{"detail": "僅發布者或超級管理員可刪除"}`
**Error 404:** `{"detail": "公告不存在"}`

## PUT /api/announcements/{id}/pin

切換置頂（僅 Role 1）

**Response 200:** `{"detail": "已置頂"}` 或 `{"detail": "已取消置頂"}`

**Error 403:** `{"detail": "僅超級管理員可操作置頂"}`
**Error 404:** `{"detail": "公告不存在"}`
