# Account Management Requirements Quality Checklist: 帳號管理

**Purpose**: 驗證帳號管理功能的需求規格品質（完整性、清晰度、一致性）
**Created**: 2026-03-30
**Feature**: [spec.md](../spec.md)
**Audience**: 主管 Review / Code Review
**Depth**: Standard

---

## Requirement Completeness（需求完整性）

- [ ] CHK001 - 是否定義了帳號列表的分頁或最大顯示數量需求？若帳號數量增長到數百個，列表如何處理？ [Gap]
- [ ] CHK002 - 是否定義了停用帳號時給被停用者的通知或提示需求（例如登入時顯示「帳號已被停用」而非「帳號或密碼錯誤」）？ [Gap]
- [ ] CHK003 - 是否定義了刪除帳號的審計日誌需求（誰在什麼時候刪了誰的帳號）？ [Gap]
- [ ] CHK004 - 是否定義了修改密碼成功後的頁面行為（停留在修改密碼頁？導向帳號管理？導向首頁？） [Completeness, Spec §US2]

## Requirement Clarity（需求清晰度）

- [ ] CHK005 - FR-009「至少有一個啟用狀態的帳號」是否明確為「啟用帳號」而非「帳號」？Edge Cases 的措辭是否需要修正？ [Clarity, Spec §FR-009 vs Edge Cases]
- [ ] CHK006 - 「二次確認」是否明確定義為瀏覽器原生 confirm 對話框，還是自訂 UI modal？ [Clarity, Spec §FR-007]
- [ ] CHK007 - US3 AS4「被停用的帳號下次發送請求時強制登出」的「下次」是否足夠明確（立即？還是下次頁面操作？API 呼叫也算？） [Clarity, Spec §US3]

## Requirement Consistency（需求一致性）

- [ ] CHK008 - 帳號管理頁面的認證保護方式是否與其他頁面（首頁、歷史紀錄）一致？ [Consistency, Spec §FR-010]
- [ ] CHK009 - 停用帳號的錯誤訊息風格是否與登入失敗的訊息風格一致？ [Consistency]
- [ ] CHK010 - 修改密碼的密碼規則（≥8 字元）是否與註冊時的規則完全一致且有明確引用？ [Consistency, Spec §FR-004]

## Acceptance Criteria Quality（驗收標準品質）

- [ ] CHK011 - SC-001「30 秒內找到並查看任意帳號」的量測起點和終點是否定義？ [Measurability, Spec §SC-001]
- [ ] CHK012 - SC-003「停用帳號後 100% 無法登入」是否涵蓋「已有的 session 也會被攔截」的驗收方式？ [Measurability, Spec §SC-003]

## Scenario Coverage（情境覆蓋）

- [ ] CHK013 - 是否定義了兩個使用者同時停用對方帳號的併發情境需求？ [Coverage, Gap]
- [ ] CHK014 - 是否定義了停用帳號後再啟用，該帳號的舊 session 是否恢復的需求？ [Coverage, Gap]
- [ ] CHK015 - 是否定義了帳號列表為空（所有帳號都被刪除到只剩自己）的顯示需求？ [Coverage, Edge Case]

## Security（安全需求）

- [ ] CHK016 - 是否定義了停用/刪除 API 的授權檢查需求（防止未登入或低權限使用者直接呼叫 API）？ [Security, Spec §FR-010]
- [ ] CHK017 - 是否定義了帳號操作（停用/刪除）的 CSRF 防護需求？ [Security, Gap]
- [ ] CHK018 - 修改密碼時是否有防止暴力破解舊密碼的需求（例如錯誤次數限制）？ [Security, Gap]

## Dependencies & Assumptions（相依性與假設）

- [ ] CHK019 - 「v1 所有使用者權限相同」的假設是否與 US3（停用別人帳號）產生安全風險？是否需要明確記錄此風險？ [Assumption, Spec §Assumptions]
- [ ] CHK020 - 「is_active 欄位已存在」的假設是否已驗證（確認 006-user-auth 有建立此欄位）？ [Dependency, Spec §Assumptions]

## Notes

- 此清單聚焦於「需求文件本身的品質」，不是測試實作是否正確
- 標記 [Gap] 的項目代表規格書中可能遺漏的需求
- CHK019 的安全風險（任何人都能停用別人）將在課題 #3 權限管理中解決
