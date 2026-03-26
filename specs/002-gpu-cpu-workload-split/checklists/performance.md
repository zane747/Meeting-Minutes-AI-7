# Performance Requirements Quality Checklist: GPU/CPU 工作負載分工最佳化

**Purpose**: 驗證效能相關需求的完整性、清晰度與可量測性（作者自檢用）
**Created**: 2026-03-26
**Feature**: [spec.md](../spec.md)

## Requirement Completeness — 效能需求是否齊全

- [ ] CHK001 - SC-001 所述「處理時間比現有方案縮短」是否定義了具體的基準值或預期改善幅度？ [Measurability, Spec §SC-001]
- [ ] CHK002 - 是否定義了 Ollama CPU 推論的可接受延遲範圍（例如摘要生成不超過 N 秒）？ [Gap]
- [ ] CHK003 - 是否定義了模型載入/卸載省略後預期節省的時間量？ [Gap, Spec §SC-001]
- [ ] CHK004 - 是否定義了不同音檔長度（1分鐘、5分鐘、30分鐘）下的效能預期？ [Completeness, Gap]
- [ ] CHK005 - 是否定義了 Whisper GPU 轉錄的效能基準（例如即時率 real-time factor）？ [Gap]
- [ ] CHK006 - 是否定義了 Diarization 步驟的效能預期或可接受延遲？ [Gap]

## Requirement Clarity — 效能需求是否明確可量測

- [ ] CHK007 - SC-001「比現有方案縮短」是否足夠明確？缺少具體百分比或秒數門檻 [Ambiguity, Spec §SC-001]
- [ ] CHK008 - Assumptions 中「CPU 推論速度在可接受範圍內」的「可接受」是否有量化定義？ [Ambiguity, Spec §Assumptions]
- [ ] CHK009 - SC-004「連續處理 3 個以上音檔不出現 OOM」中的音檔規格（大小、長度）是否定義？ [Clarity, Spec §SC-004]
- [ ] CHK010 - 「消除模型載入/卸載開銷」中的「消除」是完全消除還是顯著減少？ [Ambiguity, Spec §US1]

## Acceptance Criteria Quality — 成功標準是否可驗證

- [ ] CHK011 - SC-002「不出現 GPU 記憶體使用尖峰」是否定義了「尖峰」的量化閾值（例如 VRAM 波動不超過 X MB）？ [Measurability, Spec §SC-002]
- [ ] CHK012 - SC-004「不出現記憶體洩漏」是否定義了判定洩漏的標準（例如處理後 VRAM 回到基線 ±X MB）？ [Measurability, Spec §SC-004]
- [ ] CHK013 - SC-005 「Ollama 確實使用 GPU」的驗證方式是否在需求中明確？ [Clarity, Spec §SC-005]
- [ ] CHK014 - US1 Acceptance Scenario 2「處理時間更短」是否有可重現的量測方法定義？ [Measurability, Spec §US1]

## Scenario Coverage — 效能相關場景是否覆蓋完整

- [ ] CHK015 - 是否定義了 OLLAMA_GPU=true 時的效能預期（GPU swap 開銷仍然存在）？ [Coverage, Spec §US4]
- [ ] CHK016 - 是否定義了首次處理（冷啟動，模型首次載入）與後續處理（熱快取）的效能差異預期？ [Gap]
- [ ] CHK017 - 是否定義了並發處理時（GPU lock 排隊）的效能預期或降級行為？ [Gap]
- [ ] CHK018 - 是否定義了不同 Ollama 模型大小（2B vs 7B vs 9B）在 CPU 上的效能差異預期？ [Gap]
- [ ] CHK019 - 是否定義了 OOM fallback 到 CPU 後的效能降級預期？ [Coverage, Spec §FR-007]

## Edge Case Coverage — 效能邊界條件

- [ ] CHK020 - 是否定義了超長音檔（>1小時）的效能需求或行為限制？ [Gap]
- [ ] CHK021 - 是否定義了 VRAM 剛好足夠但邊界的場景（例如 Whisper large 在 6GB VRAM）下的效能需求？ [Gap]
- [ ] CHK022 - 是否定義了 Ollama 服務回應緩慢（非不可用）時的超時與效能影響？ [Gap]

## Dependencies & Assumptions — 效能假設是否有效

- [ ] CHK023 - 「gemma2:2b CPU 推論速度可接受」這個假設是否有基準數據支撐？ [Assumption, Spec §Assumptions]
- [ ] CHK024 - 「Whisper GPU 效能提升遠大於 Ollama GPU 效能提升」是否有量化依據？ [Assumption, Spec §Assumptions]
- [ ] CHK025 - RTX 4050 6GB VRAM 的假設是否為唯一目標硬體？是否需要為更小/更大 VRAM 定義不同效能預期？ [Assumption, Spec §Assumptions]

## Notes

- 此 checklist 聚焦效能需求的品質，而非實作驗證
- 標記 [Gap] 的項目表示需求中缺少該面向的定義
- 標記 [Ambiguity] 的項目表示現有需求措辭不夠精確
- 作者自檢時，判斷各 Gap 是需要補充還是在此功能範圍內可接受地省略
