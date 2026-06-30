def build_chunk_prompt(chunk_content: str, chunk_id: int) -> str:
    """建立單一文字分段的分析 Prompt。"""


    return f"""
```

請分析以下文件第 {chunk_id} 段內容。

請只輸出合法 JSON，不可加任何額外說明文字。

JSON 格式必須如下：

{{
"chunk_summary": "這一段的簡短摘要",
"key_points": [
"重點 1",
"重點 2"
],
"terms": [
"術語：解釋"
],
"quiz_candidates": [
{{
"question": "題目",
"answer": "答案"
}}
],
"flashcard_candidates": [
{{
"front": "正面問題",
"back": "背面答案"
}}
]
}}

規則：

1. 使用繁體中文。
2. 不可加入文件沒有提到的資訊。
3. 一般文字可適量使用 Emoji。
4. 不需要產生 Mermaid。
5. Quiz 與 Flash Card 可依內容數量產生，不足時可少於 5 題。
6. 內容不足時請保守整理，不可捏造。

文件內容如下：

{chunk_content}
"""
