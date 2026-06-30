from src.config.settings import CHUNK_OVERLAP, CHUNK_SIZE


def chunk_text(text: str) -> list[dict]:
    """依段落與句子邊界切割文字，避免在句子中間截斷。"""

    if not text:
        return []

    chunks = []
    text_length = len(text)
    start_index = 0
    chunk_id = 1

    while start_index < text_length:
        proposed_end = min(start_index + CHUNK_SIZE, text_length)
        end_index = proposed_end

        if proposed_end < text_length:
            search_text = text[start_index:proposed_end]

            break_points = [
                search_text.rfind("\n\n"),
                search_text.rfind("。"),
                search_text.rfind("！"),
                search_text.rfind("？"),
                search_text.rfind("\n"),
            ]

            best_break = max(break_points)

            if best_break > CHUNK_SIZE * 0.6:
                end_index = start_index + best_break + 1

        chunk_content = text[start_index:end_index].strip()

        if chunk_content:
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "content": chunk_content,
                    "start_index": start_index,
                    "end_index": end_index,
                    "character_count": len(chunk_content),
                }
            )
            chunk_id += 1

        if end_index >= text_length:
            break

        start_index = max(end_index - CHUNK_OVERLAP, start_index + 1)

    return chunks