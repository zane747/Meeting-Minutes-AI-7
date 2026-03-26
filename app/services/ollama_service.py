"""Ollama 摘要服務。

獨立 Service，透過 Ollama REST API 對逐字稿生成摘要與 Action Items。
可被 LocalWhisperProvider 或 API 路由直接呼叫。
"""

import json
import logging

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


async def generate_summary(transcript: str) -> dict | None:
    """透過 Ollama API 對逐字稿生成摘要與 Action Items。

    支援三態 GPU 設定：
    - "true"：強制使用 GPU
    - "false"：強制使用 CPU
    - "auto"：先嘗試 GPU，失敗時自動 fallback 到 CPU

    Args:
        transcript: 逐字稿文字。

    Returns:
        包含 summary、action_items、suggested_title 的字典，或 None（若失敗）。
    """
    # 截斷過長逐字稿，避免超出 context window
    # 粗估：1 個中文字 ≈ 2 tokens，預留 2048 tokens 給 prompt + 回應
    max_chars = (settings.OLLAMA_NUM_CTX - 2048) // 2
    if len(transcript) > max_chars:
        logger.warning(
            "逐字稿過長（%d 字），截斷至 %d 字以符合 context window",
            len(transcript),
            max_chars,
        )
        transcript = transcript[:max_chars] + "\n\n...（逐字稿已截斷）"

    prompt = OLLAMA_SUMMARY_PROMPT.format(transcript=transcript)
    gpu_mode = _resolve_gpu_mode()

    try:
        if gpu_mode == "gpu":
            parsed = await _call_ollama(prompt, use_gpu=True)
        elif gpu_mode == "cpu":
            parsed = await _call_ollama(prompt, use_gpu=False)
        else:
            # auto 模式：先嘗試 GPU，失敗時 fallback CPU
            try:
                parsed = await _call_ollama(prompt, use_gpu=True)
            except Exception as gpu_err:
                logger.warning(
                    "Ollama GPU 模式失敗（%s: %s），fallback 至 CPU",
                    type(gpu_err).__name__,
                    gpu_err,
                )
                parsed = await _call_ollama(prompt, use_gpu=False)

        logger.info("Ollama 摘要生成完成（模式=%s）", gpu_mode)
        return parsed

    except Exception as e:
        logger.warning("Ollama 摘要生成失敗：%s: %s", type(e).__name__, e, exc_info=True)
        return None


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
