"""Ollama 摘要服務。

獨立 Service，透過 Ollama REST API 對逐字稿生成摘要與 Action Items。
可被 LocalWhisperProvider 或 API 路由直接呼叫。
支援分段摘要：超長逐字稿自動分段處理後合併。
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Callable, Awaitable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OLLAMA_SYSTEM_MESSAGE = (
    "你是一位專業的會議記錄助理。無論會議使用何種語言，"
    "你的所有輸出內容（summary、action_items、suggested_title）"
    "必須使用繁體中文（Traditional Chinese）。"
    "禁止在這些欄位中出現英文、簡體中文或其他語言（人名等專有名詞及 due_date 除外）。"
    "若原文為非中文，請翻譯為繁體中文後輸出。"
)

OLLAMA_SUMMARY_PROMPT = """以下是一段會議的逐字稿，請分析後以 JSON 格式回傳：

1. summary：會議摘要（Markdown 格式），包含：
   - 會議主題
   - 重點討論事項
   - 決議事項
2. action_items：待辦事項列表，每項包含 description、assignee（若無法辨識則為 null）、due_date（若未提及則為 null）
3. suggested_title：根據會議內容建議一個簡短標題
4. semantic_analysis：語意分析，包含：
   - topics：主題分段列表，每個主題包含 title（主題名稱）、start_time（起始時間 MM:SS）、end_time（結束時間 MM:SS）。根據內容自行決定分段數量。
   - speaker_summaries：若逐字稿中有 [Speaker_X] 標籤，請為每位說話者提供訴求歸納，key 為說話者標籤，value 包含 key_points（核心主張）和 stance（立場）。若無說話者標籤則省略此欄位。

⚠️ 語言規則（最高優先級）：
- summary、action_items、suggested_title、semantic_analysis 必須全部使用繁體中文
- 若會議內容為非中文，必須翻譯為繁體中文後輸出
- 禁止在上述欄位中出現英文、簡體中文或其他語言（人名等專有名詞及 due_date 除外）

逐字稿：
{transcript}

請嚴格以下列 JSON 格式回傳：
{{
  "suggested_title": "...",
  "summary": "...",
  "action_items": [
    {{"description": "...", "assignee": "..." or null, "due_date": "..." or null}}
  ],
  "semantic_analysis": {{
    "topics": [
      {{"title": "...", "start_time": "MM:SS", "end_time": "MM:SS"}}
    ],
    "speaker_summaries": {{}}
  }}
}}"""

# --- 分段摘要相關常數與結構 ---

OLLAMA_CHUNK_SUMMARY_PROMPT = """⚠️ 這是會議逐字稿的第 {chunk_index}/{total_chunks} 段（時間範圍 {start_time} - {end_time}）。
請僅針對本段內容進行分析。

""" + OLLAMA_SUMMARY_PROMPT

OLLAMA_MERGE_PROMPT = """以下是同一場會議的多段局部摘要結果（JSON 格式），請將它們合併為一份完整的會議摘要。

合併規則：
1. summary：整合所有段落的摘要為一份連貫的完整摘要（Markdown 格式），涵蓋所有議題，去除重複內容
2. action_items：合併所有段落的待辦事項，進行語義去重（相同意思但不同措辭的項目合併為一筆）
3. suggested_title：根據所有段落的內容選擇或生成一個最適合的簡短標題
4. semantic_analysis：
   - topics：合併所有段落的主題列表，保留正確的 start_time/end_time，去除因段落重疊造成的重複主題
   - speaker_summaries：將各段同一說話者的 key_points 與 stance 整合為統一描述

{skipped_note}

各段局部摘要：
{chunk_summaries}

⚠️ 語言規則（最高優先級）：
- 所有輸出必須使用繁體中文
- 禁止出現英文、簡體中文或其他語言（人名等專有名詞及 due_date 除外）

請嚴格以下列 JSON 格式回傳：
{{
  "suggested_title": "...",
  "summary": "...",
  "action_items": [
    {{"description": "...", "assignee": "..." or null, "due_date": "..." or null}}
  ],
  "semantic_analysis": {{
    "topics": [
      {{"title": "...", "start_time": "MM:SS", "end_time": "MM:SS"}}
    ],
    "speaker_summaries": {{}}
  }}
}}"""


@dataclass
class TranscriptChunk:
    """從完整逐字稿分割出的一個片段。"""
    index: int
    content: str
    start_time: str
    end_time: str
    char_count: int


# 匹配逐字稿中的時間戳行
# 支援 MM:SS（如 [00:18 - 00:23]）與 HH:MM:SS（如 [1:05:30 - 1:05:35]）
_TIMESTAMP_LINE_RE = re.compile(
    r"^\[(\d{1,2}(?::\d{2}){1,2})\s*-\s*(\d{1,2}(?::\d{2}){1,2})\]"
)


def split_transcript(transcript: str, max_chars: int) -> list[TranscriptChunk]:
    """將逐字稿按時間戳行邊界分割成多個段落。

    分段策略：
    - 累積至 90% max_chars 時在最近的時間戳行邊界切割
    - 末段不足 500 字時併入前一段
    - 相鄰段落重疊 5 行時間戳行

    Args:
        transcript: 完整逐字稿文字。
        max_chars: 單段最大字數。

    Returns:
        分段後的 TranscriptChunk 列表。若逐字稿不超過 max_chars，回傳單一段落。
    """
    if len(transcript) <= max_chars:
        # 不需要分段
        start_time = "00:00"
        end_time = "00:00"
        for line in transcript.splitlines():
            m = _TIMESTAMP_LINE_RE.match(line.strip())
            if m:
                if start_time == "00:00":
                    start_time = m.group(1)
                end_time = m.group(2)
        return [TranscriptChunk(
            index=0, content=transcript,
            start_time=start_time, end_time=end_time,
            char_count=len(transcript),
        )]

    lines = transcript.splitlines(keepends=True)
    threshold = int(max_chars * 0.9)
    overlap_lines = 5

    # 找出所有時間戳行的索引
    ts_line_indices = []
    for i, line in enumerate(lines):
        if _TIMESTAMP_LINE_RE.match(line.strip()):
            ts_line_indices.append(i)

    if not ts_line_indices:
        # 無時間戳行，視為單一段落不分段
        return [TranscriptChunk(
            index=0, content=transcript,
            start_time="00:00", end_time="00:00",
            char_count=len(transcript),
        )]

    chunks: list[TranscriptChunk] = []
    current_start_line = 0

    while current_start_line < len(lines):
        # 累積字數直到達到閾值
        accumulated = 0
        cut_line = len(lines)  # 預設到結尾

        for i in range(current_start_line, len(lines)):
            accumulated += len(lines[i])
            if accumulated >= threshold:
                # 找到最近的時間戳行邊界（在 i 之後）
                best_cut = None
                for ts_idx in ts_line_indices:
                    if ts_idx > current_start_line and ts_idx <= i + 1:
                        best_cut = ts_idx
                if best_cut is not None:
                    cut_line = best_cut
                else:
                    # 往後找最近的時間戳行
                    for ts_idx in ts_line_indices:
                        if ts_idx > i:
                            cut_line = ts_idx
                            break
                    else:
                        cut_line = len(lines)
                break

        chunk_lines = lines[current_start_line:cut_line]
        chunk_content = "".join(chunk_lines)

        # 取得本段的起始/結束時間
        chunk_start = "00:00"
        chunk_end = "00:00"
        for line in chunk_lines:
            m = _TIMESTAMP_LINE_RE.match(line.strip())
            if m:
                if chunk_start == "00:00":
                    chunk_start = m.group(1)
                chunk_end = m.group(2)

        chunks.append(TranscriptChunk(
            index=len(chunks),
            content=chunk_content,
            start_time=chunk_start,
            end_time=chunk_end,
            char_count=len(chunk_content),
        ))

        if cut_line >= len(lines):
            break

        # 下一段從 overlap_lines 行之前開始（重疊）
        overlap_start = cut_line
        overlap_count = 0
        for ts_idx in reversed(ts_line_indices):
            if ts_idx < cut_line:
                overlap_count += 1
                if overlap_count >= overlap_lines:
                    overlap_start = ts_idx
                    break
                overlap_start = ts_idx

        current_start_line = overlap_start

    # 末段不足 500 字時併入前一段
    if len(chunks) > 1 and chunks[-1].char_count < 500:
        last = chunks.pop()
        prev = chunks[-1]
        merged_content = prev.content + last.content
        chunks[-1] = TranscriptChunk(
            index=prev.index,
            content=merged_content,
            start_time=prev.start_time,
            end_time=last.end_time,
            char_count=len(merged_content),
        )

    # 重新編號
    for i, chunk in enumerate(chunks):
        chunk.index = i

    return chunks


def _build_ollama_options(*, use_gpu: bool) -> dict:
    """根據設定建構 Ollama API 的 options 參數。

    Args:
        use_gpu: True 表示嘗試使用 GPU（省略 num_gpu），False 表示強制 CPU（num_gpu=0）。
    """
    options: dict = {"num_ctx": settings.OLLAMA_NUM_CTX}
    if not use_gpu:
        options["num_gpu"] = 0
    if settings.OLLAMA_NUM_THREAD > 0:
        options["num_thread"] = settings.OLLAMA_NUM_THREAD
    return options


def _resolve_gpu_mode() -> str:
    """根據 OLLAMA_GPU 設定回傳實際 GPU 模式。

    Returns:
        "gpu"、"cpu" 或 "auto"。
    """
    gpu_setting = settings.OLLAMA_GPU.lower()
    if gpu_setting == "true":
        return "gpu"
    if gpu_setting == "false":
        return "cpu"
    return "auto"


async def _call_ollama(prompt: str, *, use_gpu: bool) -> dict:
    """發送請求至 Ollama API 並回傳解析後的 JSON。

    Args:
        prompt: 完整的使用者 prompt。
        use_gpu: 是否使用 GPU。

    Returns:
        解析後的 JSON dict。

    Raises:
        Exception: 任何 HTTP 或 JSON 解析錯誤。
    """
    mode_label = "GPU" if use_gpu else "CPU"
    logger.info(
        "Ollama 摘要開始（模式=%s, 模型=%s, num_thread=%s）",
        mode_label,
        settings.OLLAMA_MODEL,
        settings.OLLAMA_NUM_THREAD or "auto",
    )

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": OLLAMA_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": _build_ollama_options(use_gpu=use_gpu),
            },
        )
        response.raise_for_status()

    result = response.json()
    content = result["message"]["content"]

    # 移除 LLM 可能回傳的 markdown code fence
    content = content.strip()
    if content.startswith("```"):
        first_newline = content.index("\n")
        content = content[first_newline + 1 :]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    return json.loads(content)


async def _call_ollama_with_fallback(prompt: str) -> dict:
    """根據 GPU 設定呼叫 Ollama，支援 auto fallback。

    Raises:
        Exception: 所有模式都失敗時拋出。
    """
    gpu_mode = _resolve_gpu_mode()
    if gpu_mode == "gpu":
        return await _call_ollama(prompt, use_gpu=True)
    elif gpu_mode == "cpu":
        return await _call_ollama(prompt, use_gpu=False)
    else:
        try:
            return await _call_ollama(prompt, use_gpu=True)
        except Exception as gpu_err:
            logger.warning(
                "Ollama GPU 模式失敗（%s: %s），fallback 至 CPU",
                type(gpu_err).__name__,
                gpu_err,
            )
            return await _call_ollama(prompt, use_gpu=False)


async def _summarize_chunk(
    chunk: TranscriptChunk, total_chunks: int
) -> dict | None:
    """對單一段落呼叫 LLM 產生局部摘要，失敗時重試一次。

    Args:
        chunk: 要摘要的逐字稿段落。
        total_chunks: 總段落數。

    Returns:
        局部摘要 dict，或 None（重試後仍失敗）。
    """
    prompt = OLLAMA_CHUNK_SUMMARY_PROMPT.format(
        chunk_index=chunk.index + 1,
        total_chunks=total_chunks,
        start_time=chunk.start_time,
        end_time=chunk.end_time,
        transcript=chunk.content,
    )

    for attempt in range(2):
        try:
            result = await _call_ollama_with_fallback(prompt)
            logger.info(
                "分段摘要完成：第 %d/%d 段（%s-%s）",
                chunk.index + 1, total_chunks,
                chunk.start_time, chunk.end_time,
            )
            return result
        except Exception as e:
            if attempt == 0:
                logger.warning(
                    "分段摘要失敗（第 %d/%d 段），3 秒後重試：%s",
                    chunk.index + 1, total_chunks, e,
                )
                await asyncio.sleep(3)
            else:
                logger.warning(
                    "分段摘要重試仍失敗（第 %d/%d 段），跳過：%s",
                    chunk.index + 1, total_chunks, e,
                )
    return None


async def _merge_summaries(
    chunk_results: list[dict],
    skipped_chunks: list[dict],
) -> dict | None:
    """將所有局部摘要透過一次 LLM 呼叫合併為完整摘要。

    Args:
        chunk_results: 各段的局部摘要 dict 列表。
        skipped_chunks: 被跳過的段落資訊列表 [{index, start_time, end_time}]。

    Returns:
        合併後的摘要 dict，或 None（若失敗）。
    """
    summaries_json = json.dumps(chunk_results, ensure_ascii=False, indent=2)

    skipped_note = ""
    if skipped_chunks:
        skipped_ranges = ", ".join(
            f"{s['start_time']}-{s['end_time']}" for s in skipped_chunks
        )
        skipped_note = (
            f"⚠️ 注意：以下時段的逐字稿未能成功摘要，請在 summary 中標註這些時段被遺漏：{skipped_ranges}"
        )

    prompt = OLLAMA_MERGE_PROMPT.format(
        chunk_summaries=summaries_json,
        skipped_note=skipped_note,
    )

    try:
        result = await _call_ollama_with_fallback(prompt)
        logger.info("合併摘要完成（%d 段成功，%d 段跳過）",
                     len(chunk_results), len(skipped_chunks))
        return result
    except Exception as e:
        logger.warning("合併摘要失敗，回退至簡單拼接：%s: %s", type(e).__name__, e, exc_info=True)
        return _fallback_merge(chunk_results, skipped_chunks)


def _fallback_merge(
    chunk_results: list[dict],
    skipped_chunks: list[dict],
) -> dict:
    """合併 LLM 呼叫失敗時的回退策略：簡單拼接各段局部摘要。"""
    summaries = []
    all_action_items = []
    all_topics = []
    all_speaker_summaries = {}

    for r in chunk_results:
        if r.get("summary"):
            summaries.append(r["summary"])
        all_action_items.extend(r.get("action_items", []))
        sa = r.get("semantic_analysis", {})
        all_topics.extend(sa.get("topics", []))
        for k, v in sa.get("speaker_summaries", {}).items():
            all_speaker_summaries[k] = v

    if skipped_chunks:
        skipped_ranges = ", ".join(
            f"{s['start_time']}-{s['end_time']}" for s in skipped_chunks
        )
        summaries.append(f"\n\n⚠️ 以下時段未能成功摘要：{skipped_ranges}")

    title = chunk_results[0].get("suggested_title", "") if chunk_results else ""

    return {
        "suggested_title": title,
        "summary": "\n\n---\n\n".join(summaries),
        "action_items": all_action_items,
        "semantic_analysis": {
            "topics": all_topics,
            "speaker_summaries": all_speaker_summaries,
        },
    }


# 進度回調類型：async callback(progress_pct: int, stage: str) -> None
ProgressCallback = Callable[[int, str], Awaitable[None]]


async def generate_summary(
    transcript: str,
    progress_callback: ProgressCallback | None = None,
) -> dict | None:
    """透過 Ollama API 對逐字稿生成摘要與 Action Items。

    支援分段摘要：逐字稿超過 context window 時自動分段處理後合併。
    支援進度回調：分段模式下每完成一段呼叫 callback。

    Args:
        transcript: 逐字稿文字。
        progress_callback: 可選的 async 進度回調函式。

    Returns:
        包含 summary、action_items、suggested_title 的字典，或 None（若失敗）。
    """
    # 粗估：1 個中文字 ≈ 2 tokens，預留 2048 tokens 給 prompt + 回應
    max_chars = (settings.OLLAMA_NUM_CTX - 2048) // 2

    chunks = split_transcript(transcript, max_chars)

    if len(chunks) == 1:
        # 短逐字稿：單次摘要模式（原有流程）
        prompt = OLLAMA_SUMMARY_PROMPT.format(transcript=transcript)
        try:
            parsed = await _call_ollama_with_fallback(prompt)
            logger.info("Ollama 摘要生成完成（單次模式）")
            return parsed
        except Exception as e:
            logger.warning("Ollama 摘要生成失敗：%s: %s", type(e).__name__, e, exc_info=True)
            return None

    # 分段摘要模式
    total = len(chunks)
    logger.info("啟動分段摘要模式：%d 段（逐字稿 %d 字，max_chars=%d）",
                total, len(transcript), max_chars)

    chunk_results: list[dict] = []
    skipped_chunks: list[dict] = []

    for chunk in chunks:
        if progress_callback:
            # 60%-78% 分配給各段
            pct = 60 + int(18 * chunk.index / total)
            await progress_callback(
                pct, f"生成摘要中（第 {chunk.index + 1}/{total} 段）..."
            )

        result = await _summarize_chunk(chunk, total)
        if result:
            chunk_results.append(result)
        else:
            skipped_chunks.append({
                "index": chunk.index,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
            })

    if not chunk_results:
        logger.warning("所有分段摘要均失敗")
        return None

    # 合併階段
    if progress_callback:
        await progress_callback(78, "合併摘要中...")

    merged = await _merge_summaries(chunk_results, skipped_chunks)

    if merged:
        logger.info(
            "分段摘要合併完成（%d/%d 段成功）",
            len(chunk_results), total,
        )
    return merged


async def is_available() -> bool:
    """檢查 Ollama 服務是否可用，並驗證設定的模型已下載。

    Returns:
        True 表示 Ollama 服務可連線且模型已就緒。
    """
    if not settings.OLLAMA_ENABLED:
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()

            # 檢查設定的模型是否已下載
            data = resp.json()
            model_names = [m.get("name", "") for m in data.get("models", [])]
            target = settings.OLLAMA_MODEL
            if target not in model_names:
                # 嘗試比對不含 tag 的名稱（如 "gemma2" vs "gemma2:latest"）
                base_names = [n.split(":")[0] for n in model_names]
                target_base = target.split(":")[0]
                if target_base not in base_names:
                    logger.warning(
                        "Ollama 模型 '%s' 尚未下載，請執行 `ollama pull %s`",
                        target,
                        target,
                    )

            return True
    except Exception:
        return False
