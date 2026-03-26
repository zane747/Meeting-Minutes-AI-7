"""分段摘要邏輯的單元測試。"""

import pytest

from app.services.ollama_service import TranscriptChunk, split_transcript


def _make_transcript(lines: list[str]) -> str:
    """將行列表組合為逐字稿字串。"""
    return "\n".join(lines)


def _make_timestamped_lines(count: int, start_min: int = 0) -> list[str]:
    """產生指定數量的帶時間戳行。"""
    lines = []
    for i in range(count):
        m = start_min + i
        s1 = f"{m:02d}:00"
        s2 = f"{m:02d}:05"
        lines.append(f"[{s1} - {s2}] 這是第{i+1}行的測試內容，模擬會議對話。")
    return lines


class TestSplitTranscript:
    """split_transcript 函式測試。"""

    def test_short_transcript_no_split(self):
        """短逐字稿不應分段。"""
        lines = _make_timestamped_lines(5)
        transcript = _make_transcript(lines)
        chunks = split_transcript(transcript, max_chars=10000)
        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert chunks[0].content == transcript
        assert chunks[0].start_time == "00:00"
        assert chunks[0].end_time == "04:05"

    def test_long_transcript_splits(self):
        """超過 max_chars 的逐字稿應被分段。"""
        lines = _make_timestamped_lines(100)
        transcript = _make_transcript(lines)
        # 設定一個會觸發分段的 max_chars
        max_chars = len(transcript) // 3
        chunks = split_transcript(transcript, max_chars)
        assert len(chunks) >= 2
        # 所有段落都應有正確的 index
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
            assert chunk.char_count > 0
            assert chunk.start_time != ""
            assert chunk.end_time != ""

    def test_last_chunk_merged_if_too_short(self):
        """末段不足 500 字應併入前一段。"""
        # 產生足夠行數讓最後一段很短
        lines = _make_timestamped_lines(50)
        transcript = _make_transcript(lines)
        single_line_len = len(lines[0]) + 1  # +1 for \n
        # 設定 max_chars 使得最後剩下不到 500 字
        max_chars = single_line_len * 45
        chunks = split_transcript(transcript, max_chars)
        # 最後一段應該不小於 500 字（如果整體有足夠長度）
        if len(chunks) > 1:
            assert chunks[-1].char_count >= 500 or chunks[-1].char_count == len(transcript)

    def test_overlap_between_chunks(self):
        """相鄰段落應有重疊內容。"""
        lines = _make_timestamped_lines(100)
        transcript = _make_transcript(lines)
        max_chars = len(transcript) // 4
        chunks = split_transcript(transcript, max_chars)
        if len(chunks) >= 2:
            # 檢查第一段的末尾幾行是否出現在第二段的開頭
            first_lines = chunks[0].content.splitlines()
            second_lines = chunks[1].content.splitlines()
            # 至少有一些重疊行
            overlap_found = False
            for line in first_lines[-5:]:
                if line in second_lines[:10]:
                    overlap_found = True
                    break
            assert overlap_found, "相鄰段落之間應有重疊內容"

    def test_no_timestamp_returns_single_chunk(self):
        """無時間戳格式的逐字稿不應分段。"""
        transcript = "這是一段沒有時間戳的逐字稿。\n" * 1000
        chunks = split_transcript(transcript, max_chars=500)
        assert len(chunks) == 1

    def test_chunk_start_end_times(self):
        """每段的 start_time 和 end_time 應正確對應段落內容。"""
        lines = _make_timestamped_lines(20, start_min=5)
        transcript = _make_transcript(lines)
        max_chars = len(transcript) // 2
        chunks = split_transcript(transcript, max_chars)
        for chunk in chunks:
            # start_time 應在 end_time 之前或相等
            assert chunk.start_time <= chunk.end_time

    def test_single_line_transcript(self):
        """極短逐字稿（只有一行）應回傳單一段落。"""
        transcript = "[00:00 - 00:05] 測試"
        chunks = split_transcript(transcript, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0].start_time == "00:00"
        assert chunks[0].end_time == "00:05"

    def test_output_format_consistency(self):
        """分段後每個 chunk 的結構應完整。"""
        lines = _make_timestamped_lines(30)
        transcript = _make_transcript(lines)
        chunks = split_transcript(transcript, max_chars=len(transcript) // 2)
        for chunk in chunks:
            assert isinstance(chunk, TranscriptChunk)
            assert isinstance(chunk.index, int)
            assert isinstance(chunk.content, str)
            assert isinstance(chunk.char_count, int)
            assert chunk.char_count == len(chunk.content)
