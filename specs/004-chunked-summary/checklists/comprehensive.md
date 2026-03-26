# Comprehensive Checklist: 分段摘要合併

**Purpose**: 全面檢查分段摘要功能的需求品質 — 分段邏輯、LLM 整合、容錯韌性
**Created**: 2026-03-26
**Feature**: [spec.md](../spec.md)
**Depth**: 標準級 | **Audience**: 自我檢查

## 需求完整性（Requirement Completeness）

- [ ] CHK001 - 分段觸發的閾值計算公式是否明確記錄？（max_chars 的推導邏輯） [Completeness, Spec §FR-001]
- [ ] CHK002 - 是否定義了不同長度會議的預期段落數範圍？（如 30 分鐘約幾段、2 小時約幾段） [Completeness, Spec §Assumptions]
- [ ] CHK003 - 末段合併的字數門檻（500 字）是否在需求中記錄？ [Completeness, Gap]
- [ ] CHK004 - 重疊行數（5 行）的選擇依據是否在需求或研究中說明？ [Completeness, research.md §R-002]
- [ ] CHK005 - 進度回報的百分比分配邏輯（60%-78% 各段、78%-80% 合併）是否明確定義？ [Completeness, Spec §FR-008]
- [ ] CHK006 - 合併步驟的 context window 用量估算是否在需求中記錄？（12 段局部摘要是否超出 32K） [Completeness, research.md §R-004]

## 需求清晰度（Requirement Clarity）

- [ ] CHK007 - FR-002 中「語義邊界」是否有明確定義？是時間戳行邊界、靜默間隔、還是其他？ [Clarity, Spec §FR-002]
- [ ] CHK008 - FR-010 中「上下文重疊」的具體實作方式是否足夠清晰？（固定行數 vs 固定字數 vs 百分比） [Clarity, Spec §FR-010]
- [ ] CHK009 - FR-012 中「標註遺漏的時段範圍」的呈現格式是否定義？（在 summary Markdown 中如何標示） [Clarity, Spec §FR-012]
- [ ] CHK010 - SC-003 中「N+1 倍」的 N 是否明確定義為分段數？合併步驟是否計入？ [Clarity, Spec §SC-003]
- [ ] CHK011 - SC-005 中「可讀性評分」是否有可操作的量化標準或判斷方式？ [Measurability, Spec §SC-005]

## 需求一致性（Requirement Consistency）

- [ ] CHK012 - FR-004/FR-005/FR-006 皆描述合併呼叫中的不同面向，三者是否一致指向「單一 LLM 呼叫」？ [Consistency, Spec §FR-004/005/006]
- [ ] CHK013 - spec 中的 Key Entities（TranscriptChunk）與 data-model.md 中的欄位定義是否一致？ [Consistency, Spec §Key Entities vs data-model.md]
- [ ] CHK014 - 合併 prompt 中對 speaker_summaries 的指示是否與 spec §FR-006 的主題合併要求一致？ [Consistency, Spec §FR-006]
- [ ] CHK015 - tasks.md 中的 Phase 依賴關係是否與 spec 中 User Story 的優先級排序一致？ [Consistency, tasks.md §Dependencies]

## 分段邏輯需求品質

- [ ] CHK016 - 90% max_chars 閾值的選擇是否有合理依據？是否考慮了 prompt 本身佔用的 token？ [Clarity, research.md §R-001]
- [ ] CHK017 - 無時間戳格式的逐字稿的處理方式是否在需求中明確定義？ [Gap, Spec §Edge Cases]
- [ ] CHK018 - 分段切割點落在議題中間的緩解策略是否足夠具體？（僅靠 5 行重疊是否充分） [Coverage, Spec §Edge Cases]
- [ ] CHK019 - 是否定義了分段後每段的最小字數下限？（避免產出過短的無意義段落） [Gap]
- [ ] CHK020 - 時間戳行的正規表達式是否涵蓋所有可能的格式？（如 HH:MM:SS、M:SS 等） [Completeness, Gap]

## LLM 整合需求品質

- [ ] CHK021 - 分段 prompt（OLLAMA_CHUNK_SUMMARY_PROMPT）是否清楚告知 LLM 本段只是整體的一部分？ [Clarity, research.md §R-003]
- [ ] CHK022 - 合併 prompt（OLLAMA_MERGE_PROMPT）中「語義去重」的判斷標準是否足夠明確？ [Clarity, Spec §FR-005]
- [ ] CHK023 - 合併 prompt 是否明確要求 LLM 保持與單次摘要相同的 JSON 格式？ [Consistency, Spec §FR-009]
- [ ] CHK024 - 是否定義了局部摘要 JSON 解析失敗時的處理方式？（如 LLM 回傳非法 JSON） [Gap, Exception Flow]
- [ ] CHK025 - 是否考慮了合併步驟本身失敗的回退策略？（所有局部摘要已完成但合併失敗） [Gap, Exception Flow]

## 容錯與韌性需求品質

- [ ] CHK026 - FR-011 中「重試一次」的等待間隔是否定義？還是立即重試？ [Clarity, Spec §FR-011]
- [ ] CHK027 - 若所有段落都失敗（chunk_results 為空），需求是否定義了預期行為？ [Coverage, Spec §Edge Cases]
- [ ] CHK028 - 部分段落跳過後的合併摘要品質要求是否定義？（如跳過 3/5 段，摘要仍有價值嗎） [Gap]
- [ ] CHK029 - Ollama 服務在處理途中完全斷線的場景是否在需求中涵蓋？ [Coverage, Gap]
- [ ] CHK030 - GPU lock 在分段模式下的持有策略是否明確？（整個分段流程期間持有 vs 每段獨立獲取） [Gap, plan.md]

## 場景覆蓋度（Scenario Coverage）

- [ ] CHK031 - 剛好在 context window 邊界的逐字稿（如差 100 字就超過）的判斷策略是否明確？ [Coverage, Spec §Edge Cases]
- [ ] CHK032 - 單一議題但非常冗長的會議，分段合併後避免重複摘要的策略是否在需求中定義？ [Coverage, Spec §Edge Cases]
- [ ] CHK033 - 2 小時上限的超長會議邊界行為是否定義？（超過 2 小時是拒絕、警告還是盡力處理） [Gap, Spec §Assumptions]
- [ ] CHK034 - 是否考慮了同時有多場長會議進入分段模式時的資源競爭場景？ [Gap, Non-Functional]
- [ ] CHK035 - 短會議路徑（單次模式）與長會議路徑（分段模式）的輸出格式一致性是否有驗收標準？ [Measurability, Spec §FR-009]

## Notes

- Check items off as completed: `[x]`
- 此 checklist 為需求品質自查工具，非實作驗證清單
- 標記為 [Gap] 的項目代表需求中可能遺漏的面向
- 標記為 [Clarity] 的項目代表需求描述可能不夠精確
