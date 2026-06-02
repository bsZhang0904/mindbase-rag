from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = """你是 MindBase 知识库助手。请严格根据以下「参考资料」回答用户问题。

规则：
1. 仅使用参考资料中的信息，不要编造。
2. 若资料不足以回答，请明确说「根据现有资料无法回答」。
3. 回答中使用 [1][2] 标注引用，对应参考资料编号。
4. 回答简洁、结构化，使用中文。"""


def build_context(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        page_info = f"，第{chunk.page_number}页" if chunk.page_number else ""
        parts.append(
            f"[{i}] （来源：{chunk.document_title}{page_info}）\n{chunk.content}"
        )
    return "\n\n".join(parts)


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return f"## 参考资料\n（无相关资料）\n\n## 用户问题\n{question}"
    return f"## 参考资料\n{build_context(chunks)}\n\n## 用户问题\n{question}"


class Generator:
    def __init__(self) -> None:
        self.use_mock = settings.MOCK_MODE or not settings.LLM_API_KEY
        if not self.use_mock:
            self.client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "根据现有资料无法回答该问题。请先上传相关文档并等待索引完成。"

        if self.use_mock:
            summary = chunks[0].content[:200]
            refs = "".join(f"[{i}]" for i in range(1, min(len(chunks), 3) + 1))
            return f"根据资料，{summary}... {refs}\n\n（演示模式：配置 LLM_API_KEY 后可获得完整 AI 回答）"

        user_prompt = build_user_prompt(question, chunks)
        response = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or "抱歉，未能生成回答。"

    async def generate_stream(self, question: str, chunks: list[RetrievedChunk]) -> AsyncIterator[str]:
        if not chunks:
            yield "根据现有资料无法回答该问题。请先上传相关文档并等待索引完成。"
            return

        if self.use_mock:
            answer = await self.generate(question, chunks)
            for char in answer:
                yield char
            return

        user_prompt = build_user_prompt(question, chunks)
        stream = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
