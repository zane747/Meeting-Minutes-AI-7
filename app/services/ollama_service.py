"""Ollama 摘要服務。

獨立 Service，透過 Ollama REST API 對逐字稿生成摘要與 Action Items。
可被 LocalWhisperProvider 或 API 路由直接呼叫。
"""

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OLLAMA_SUMMARY_PROMPT = """你是一位專業的會議記錄助理。今天的日期是 {today}。以下是一段會議的逐字稿，請分析後以 JSON 格式回傳：

1. summary：會議摘要（Markdown 格式），包含：
   - 會議主題
   - 重點討論事項
   - 決議事項
2. action_items：待辦事項列表，每項包含 description、assignee（若無法辨識則為 null）、due_date（若未提及則為 null）
3. suggested_title：根據會議內容建議一個簡短標題

所有輸出必須使用繁體中文。

逐字稿：
{transcript}

請嚴格以下列 JSON 格式回傳：
{{
  "suggested_title": "...",
  "summary": "...",
  "action_items": [
    {{"description": "...", "assignee": "..." or null, "due_date": "..." or null}}
  ]
}}"""


async def generate_summary(transcript: str) -> dict | None:
    """透過 Ollama API 對逐字稿生成摘要與 Action Items。

    Args:
        transcript: 逐字稿文字。

    Returns:
        包含 summary、action_items、suggested_title 的字典，或 None（若失敗）。
    """
    from datetime import date
    prompt = OLLAMA_SUMMARY_PROMPT.format(transcript=transcript, today=date.today().isoformat())

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {
                        "num_ctx": settings.OLLAMA_NUM_CTX,
                    },
                },
            )
            response.raise_for_status()

        result = response.json()
        content = result["message"]["content"]

        # 移除 LLM 可能回傳的 markdown code fence
        content = content.strip()
        if content.startswith("```"):
            # 移除開頭的 ```json 或 ``` 行
            first_newline = content.index("\n")
            content = content[first_newline + 1:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed = json.loads(content)
        logger.info("Ollama 摘要生成完成")
        return parsed

    except Exception as e:
        logger.warning(f"Ollama 摘要生成失敗：{e}")
        return None


async def is_available() -> bool:
    """檢查 Ollama 服務是否可用。

    Returns:
        True 表示 Ollama 服務可連線。
    """
    if not settings.OLLAMA_ENABLED:
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            return True
    except Exception:
        return False
