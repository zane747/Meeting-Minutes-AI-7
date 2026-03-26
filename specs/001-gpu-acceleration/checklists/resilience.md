# 容錯/降級需求品質 Checklist: GPU 加速模型推論

**Purpose**: 驗證容錯與降級相關需求的完整性、清晰度與一致性（PR Review 層級）
**Created**: 2026-03-25
**Feature**: [spec.md](../spec.md)

## 需求完整性 (Requirement Completeness)

- [x] CHK001 - FR-004 是否定義了模型降級的完整順序（從哪個模型降到哪個模型）？ [Completeness, Spec §FR-004] — 已補充：medium → small → base → tiny → CPU fallback
- [x] CHK002 - 是否明確規範了降級嘗試的最大次數或終止條件？ [Gap] — 已補充至 FR-004：遍歷 fallback 列表，全部 OOM 退 CPU，CPU 也失敗標記 FAILED
- [x] CHK003 - Diarization（說話者辨識）模型的 OOM 降級策略是否在需求中定義？ [Gap, Spec §FR-003] — 已新增 FR-010：直接退回 CPU 重載同一模型
- [x] CHK004 - 是否定義了降級事件的日誌記錄格式與內容要求？ [Clarity, Spec §FR-004] — 已補充：觸發時間、原始模型、降級後模型、降級原因、處理任務 ID
- [x] CHK005 - 是否定義了硬體加速資源釋放失敗時的處理方式？ [Gap, Spec §FR-009] — 已補充：記錄警告並繼續處理，不導致服務中斷
- [x] CHK006 - 是否定義了排隊中的任務在排隊等待期間的超時機制？ [Gap, Spec §FR-005] — 已在 Assumptions 明確記錄：單機桌面場景暫不設超時

## 需求清晰度 (Requirement Clarity)

- [x] CHK007 - US1 Acceptance Scenario 3 與 Clarification 決議是否一致？ [Conflict, Spec §US1-AS3] — 已更新 AS3 為兩階段降級描述
- [x] CHK008 - SC-003「5 秒」範圍是否明確？ [Ambiguity, Spec §SC-003] — 已修改：從捕捉例外到替代模型成功載入，不含推論時間
- [x] CHK009 - US2 Acceptance Scenario 2「合理協調」是否量化？ [Ambiguity, Spec §US2-AS2] — 已更新為排隊機制具體描述
- [x] CHK010 - FR-004「記憶體不足」的判定標準是否明確？ [Clarity, Spec §FR-004] — 已補充：以捕捉 OOM 例外為準
- [x] CHK011 - US1 Acceptance Scenario 1 是否引用量化門檻？ [Ambiguity, Spec §US1-AS1] — 已更新引用 SC-001 的 50%

## 需求一致性 (Requirement Consistency)

- [x] CHK012 - Edge Case 與 FR-004 用詞是否一致？ [Consistency] — 已統一為引用 FR-004 的降級順序描述
- [x] CHK013 - US3「系統介面中」vs「API 端點」用語是否統一？ [Conflict, Spec §US3] — 已更新 US3 為「系統狀態 API 端點」
- [x] CHK014 - Ollama 與排隊機制的關係是否明確？ [Consistency, Spec §Assumptions] — 已更新 Assumption：Ollama 不在排隊範圍內，但推論前主動卸載

## 情境覆蓋 (Scenario Coverage)

- [x] CHK015 - 是否定義了處理中 GPU 被外部程式佔用的需求？ [Gap, Spec §Edge Cases] — 已補充：適用一般 OOM 降級策略，不區分原因
- [x] CHK016 - 是否定義了驅動程式不相容時的行為？ [Gap, Spec §Edge Cases] — 已補充：GPU 偵測回傳不可用，自動使用 CPU
- [x] CHK017 - 是否定義了 CPU fallback 後重新嘗試 GPU 的需求？ [Gap] — 已補充至 FR-004 與 Edge Cases：降級僅影響當次請求
- [x] CHK018 - Whisper + Diarization 同時使用 GPU 的需求是否明確？ [Clarity, Spec §FR-005] — 已補充：排隊機制保證不同時佔用
- [x] CHK019 - DEVICE=cuda 但 GPU 不可用時的錯誤訊息需求？ [Gap, Spec §FR-006] — 已補充至 FR-006
- [x] CHK020 - 降級過程的使用者回饋是否定義？ [Gap] — 已補充至 FR-004：靜默進行，可事後透過 API 查詢

## 驗收標準可量測性 (Acceptance Criteria Measurability)

- [x] CHK021 - SC-005「成功率 100%」的定義是否明確？ [Measurability, Spec §SC-005] — 已修改：不出現未捕捉例外，最終產出結果
- [x] CHK022 - SC-003 量測起終點是否明確？ [Measurability, Spec §SC-003] — 已修改：從捕捉例外到替代模型載入完成
- [x] CHK023 - SC-001 基準測量條件是否指定？ [Measurability, Spec §SC-001] — 已補充：同硬體、同音檔、冷啟動、3 次平均

## 邊界條件 (Edge Case Coverage)

- [x] CHK024 - 是否定義了 VRAM 臨界值行為？ [Edge Case, Gap] — 已補充至 Assumptions：由 OOM 例外機制處理，推論中途 OOM 同樣觸發降級
- [x] CHK025 - 是否定義了模型降級後品質下降的預期？ [Gap] — 已補充至 Assumptions：優先完成處理，使用者可查詢實際模型大小
- [x] CHK026 - 是否定義了 PyTorch 未安裝時的行為？ [Edge Case, Gap] — 已補充至 FR-001 與 Edge Cases
- [x] CHK027 - Whisper + Diarization 都 OOM 的處理順序？ [Edge Case, Spec §FR-005] — 已補充至 FR-005：Whisper 先執行，各自獨立處理 OOM

## Notes

- 所有 27 項均已通過 — spec.md 已更新修正所有發現的問題
- 新增 FR-010（Diarization OOM 降級策略）
- 新增 3 條 Assumptions（VRAM 臨界值、品質預期、排隊超時）
- 修正 2 處 Conflict（US1-AS3 兩階段降級、US3 介面→API）
- 量化 4 處 Ambiguity（SC-001 基準、SC-003 範圍、SC-005 定義、US2-AS2 協調方式）
