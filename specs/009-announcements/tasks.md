# Tasks: 最新消息 / 公告訊息

**Input**: `specs/009-announcements/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/api.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行執行（不同檔案、無依賴）
- **[Story]**: 對應 spec.md 的使用者情境

---

## Phase 1: Setup

**Purpose**: 註冊路由、準備基礎結構

- [x] T001 在 app/main.py 註冊 announcements API router

**Checkpoint**: 路由已掛載，可開始實作

---

## Phase 2: Foundational（基礎建設）

**Purpose**: 資料模型與 Pydantic schemas，所有使用者故事都依賴這些

- [x] T002 在 app/models/database_models.py 新增 Announcement 模型（含 creator relationship）
- [x] T003 [P] 在 app/models/schemas.py 新增公告相關 Pydantic 模型（AnnouncementCreate、AnnouncementUpdate、AnnouncementResponse、AnnouncementListItem）

**Checkpoint**: 資料模型就緒，可開始實作使用者故事

---

## Phase 3: US-01 + US-02 + US-03 — 發布公告、查看列表、查看詳情（P1）🎯 MVP

**Goal**: 管理員可發布公告，所有使用者可瀏覽列表和查看詳情

**Independent Test**: 登入管理員帳號 → 建立一則公告 → 切換一般使用者帳號 → 在列表中看到該公告 → 點進去看到完整內容

### Implementation

- [x] T004 [US1] 在 app/api/routes/announcements.py 建立 API router 與 POST /api/announcements 端點（含 require_role 權限檢查）
- [x] T005 [US2] 在 app/api/routes/announcements.py 新增 GET /api/announcements 端點（列表，置頂優先 + 時間倒序）
- [x] T006 [P] [US2] 在 app/templates/announcements.html 建立公告列表頁（含標題搜尋、空狀態處理、管理員可見「發布」按鈕）
- [x] T007 [P] [US1] 在 app/templates/announcement_form.html 建立公告表單頁（標題 255 字元、內容 5000 字元限制）
- [x] T008 [US3] 在 app/api/routes/announcements.py 新增 GET /api/announcements/{id} 端點
- [x] T009 [P] [US3] 在 app/templates/announcement_detail.html 建立公告詳情頁（顯示標題、內容、發布者、時間、管理員可見編輯/刪除按鈕）
- [x] T010 [US2] 在 app/api/routes/pages.py 新增公告頁面路由（/announcements、/announcements/create、/announcements/{id}）
- [x] T011 [US2] 在 app/templates/base.html 導覽列新增「最新消息」連結（所有登入使用者可見）

**Checkpoint**: MVP 完成 — 可發布、瀏覽、查看公告

---

## Phase 4: US-04 + US-05 — 編輯與刪除公告（P2）

**Goal**: 管理員可編輯和刪除自己的公告，超級管理員可操作所有公告

**Independent Test**: 管理員建立公告 → 編輯標題和內容 → 確認 updated_at 更新 → 刪除公告 → 確認列表中消失

### Implementation

- [x] T012 [US4] 在 app/api/routes/announcements.py 新增 PUT /api/announcements/{id} 端點（含 _check_announcement_owner 權限檢查）
- [x] T013 [P] [US4] 在 app/templates/announcement_form.html 擴充為建立/編輯共用表單（編輯模式預填現有內容）
- [x] T014 [US4] 在 app/api/routes/pages.py 新增 /announcements/{id}/edit 頁面路由（含權限檢查）
- [x] T015 [US5] 在 app/api/routes/announcements.py 新增 DELETE /api/announcements/{id} 端點（含權限檢查）
- [x] T016 [US5] 在 app/templates/announcement_detail.html 加上刪除按鈕的 JS confirm 對話框與 fetch DELETE 邏輯

**Checkpoint**: 編輯與刪除功能完成

---

## Phase 5: US-06 — 置頂功能（P2）

**Goal**: 超級管理員可置頂/取消置頂公告

**Independent Test**: 超級管理員將公告設為置頂 → 列表中該公告排最前 → 取消置頂 → 回到正常排序

### Implementation

- [x] T017 [US6] 在 app/api/routes/announcements.py 新增 PUT /api/announcements/{id}/pin 端點（僅 Role 1）
- [x] T018 [US6] 在 app/templates/announcements.html 列表頁為超級管理員顯示置頂/取消置頂按鈕（已在列表卡片顯示置頂標籤）
- [x] T019 [US6] 在 app/templates/announcement_detail.html 詳情頁為超級管理員顯示置頂/取消置頂按鈕

**Checkpoint**: 置頂功能完成

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 收尾與品質確認

- [x] T020 確認所有 API 端點都有 Depends(get_current_user) 權限檢查
- [x] T021 [P] 確認前後端欄位名稱對齊（Pydantic schema vs Jinja2 模板 vs JS fetch）
- [x] T022 手動測試完整流程：建立 → 列表 → 詳情 → 編輯 → 置頂 → 刪除

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（Setup）**: 無依賴，立即開始
- **Phase 2（Foundational）**: 依賴 Phase 1 完成
- **Phase 3（US-01/02/03）**: 依賴 Phase 2 完成 — **這是 MVP**
- **Phase 4（US-04/05）**: 依賴 Phase 3 完成
- **Phase 5（US-06）**: 依賴 Phase 3 完成（可與 Phase 4 平行）
- **Phase 6（Polish）**: 依賴所有功能完成

### Parallel Opportunities

- T003 與 T002 可平行（不同檔案）
- T006、T007、T009 可平行（不同模板檔案）
- T013 與 T015 可平行（不同端點 + 不同模板）
- Phase 4 與 Phase 5 可平行（獨立功能）

---

## Implementation Strategy

### MVP First（Phase 1-3）

1. 完成 Setup + Foundational
2. 完成 US-01/02/03 → 測試：可發布、瀏覽、查看
3. **停下來驗證** MVP 是否正常運作

### Incremental Delivery

4. 加入 US-04/05 → 測試：可編輯、刪除
5. 加入 US-06 → 測試：置頂功能
6. Polish → 最終驗收
