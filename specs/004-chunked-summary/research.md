# Research: 分段摘要合併

**Feature**: 004-chunked-summary
**Date**: 2026-03-26

## R-001: 逐字稿分段策略

**Decision**: 以時間戳為主要切割依據，按字數累積分段，在時間戳行邊界切割

**Rationale**:
- 現有逐字稿格式為 `[MM:SS - MM:SS] 內容`，每行都有時間標記
- 按時間戳行切割可確保不會在一句話中間斷開
- 每段累積字數達到 `max_chars` 的 90%（預留 10% 重疊空間）時，在最近的時間戳行邊界切割
- 最後一段若不足 500 字，併入前一段以避免產出無意義摘要

**Alternatives considered**:
- 純字數切割：簡單但可能在句子中間斷開，造成語意不完整
- LLM 自動分段：需要額外 LLM 呼叫，且本身可能超出 context window
- 靜默間隔偵測：需要音檔資訊，逐字稿層級無法取得

## R-002: 上下文重疊策略

**Decision**: 相鄰段落重疊最後/最前 5 行時間戳行

**Rationale**:
- 固定行數比固定字數更容易實作且可預測
- 5 行（約 10-30 秒的對話）足以讓 LLM 理解跨段議題的延續
- 重疊內容在合併階段會被 LLM 自然去重

**Alternatives considered**:
- 固定字數重疊（如 500 字）：不同語速下涵蓋的語意量差異大
- 無重疊：議題被切割時摘要會遺漏關鍵轉折
- 段落級重疊（整段重複）：浪費 context window 容量

## R-003: 分段摘要 Prompt 設計

**Decision**: 分段摘要使用與現有單次摘要相同的 prompt 結構，合併階段使用專用 merge prompt

**Rationale**:
- 分段摘要 prompt 沿用現有 `OLLAMA_SUMMARY_PROMPT`，僅在前方加入段落資訊（如「這是第 2/4 段，時間範圍 05:00-12:30」）
- 合併 prompt 接收所有局部摘要的 JSON 結果，要求 LLM 整合為單一 JSON 輸出
- 沿用相同格式可確保 FR-009（格式一致性）

**Alternatives considered**:
- 分段使用精簡 prompt（只提取關鍵字）再合併：品質不穩定，可能遺漏決議
- 每段使用不同結構的 prompt：增加維護複雜度

## R-004: 合併摘要的 context window 使用

**Decision**: 合併呼叫送入所有局部摘要的 JSON 結果（非原始逐字稿）

**Rationale**:
- 每段局部摘要約 500-1000 字，12 段最多約 12000 字
- 合併 prompt + 12 段摘要 ≈ 約 26000 tokens，在 gemma2 的 context window 內（需將 `OLLAMA_NUM_CTX` 調高至 32768）
- 若局部摘要總長仍超出限制，可先進行兩兩合併（hierarchical merge）

**Alternatives considered**:
- 只做程式拼接不用 LLM：無法去重和產出連貫敘述
- 逐段遞增式合併（每次合併新段落到已合併結果）：呼叫次數更多，且前段資訊在多次處理後可能失真

## R-005: 失敗重試與部分結果策略

**Decision**: 單段失敗重試一次，仍失敗則跳過，合併時標註遺漏

**Rationale**:
- 已在 clarify 階段確認（選項 B）
- 重試一次可處理偶發性的 Ollama 超時或記憶體不足
- 跳過失敗段落並標註時段範圍，讓使用者知道哪些內容未被摘要
- 合併 prompt 中需告知 LLM 哪些段落被跳過

**Alternatives considered**:
- 全部失敗：長會議成本太高，不合理
- 降級為逐字稿附加：增加前端顯示複雜度

## R-006: 進度回報機制

**Decision**: 在現有進度系統中細分 60%-80% 區間，每完成一段更新一次

**Rationale**:
- 現有進度：60% = "生成摘要中..."，80% = "儲存分析結果中..."
- 分段模式下，60%-78% 平均分配給各段（如 4 段：60%, 64.5%, 69%, 73.5%）
- 78%-80% 保留給合併步驟
- 進度訊息改為「生成摘要中（第 X/Y 段）...」

**Alternatives considered**:
- 新增獨立的進度區間（如 60%-90%）：需要調整後續階段的進度值，影響範圍大
- 不細分進度：使用者會以為系統卡住

## R-007: OLLAMA_NUM_CTX 設定調整

**Decision**: 建議將 `OLLAMA_NUM_CTX` 預設值從 16384 提高至 32768，以支援合併摘要

**Rationale**:
- gemma2 模型在 RTX 4050 (6GB VRAM) 上可支援 32K context
- 合併步驟需要容納 8-12 段局部摘要（每段約 500-1000 字），需要更大的 context window
- 分段摘要的每段仍使用原有的 max_chars 計算邏輯

**Alternatives considered**:
- 保持 16384 但限制合併段數：可能導致超長會議的局部摘要無法完整合併
- 動態調整 context：Ollama API 不支援動態切換
