"""Quick end-to-end API smoke test."""
import asyncio
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
SAMPLE = Path(__file__).resolve().parents[2] / "sample_docs" / "rag_intro.md"


async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        health = (await client.get("http://127.0.0.1:8000/health")).json()
        print(f"Health: {health}")

        email = f"e2e_{int(time.time())}@test.com"
        await client.post(f"{BASE}/auth/register", json={"email": email, "username": f"u{int(time.time())}", "password": "Test123456"})
        login = (await client.post(f"{BASE}/auth/login", json={"email": email, "password": "Test123456"})).json()
        token = login["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        kb = (await client.post(f"{BASE}/knowledge-bases", headers=headers, json={"name": "E2E测试", "description": "重启验证"})).json()
        kb_id = kb["data"]["id"]
        print(f"KB: {kb_id}")

        with SAMPLE.open("rb") as f:
            upload = (
                await client.post(
                    f"{BASE}/knowledge-bases/{kb_id}/documents",
                    headers=headers,
                    files={"file": ("rag_intro.md", f, "text/markdown")},
                )
            ).json()
        doc_id = upload["data"]["document_id"]
        print(f"Uploaded doc: {doc_id}")

        for i in range(30):
            await asyncio.sleep(2)
            doc = (await client.get(f"{BASE}/documents/{doc_id}", headers=headers)).json()["data"]
            print(f"Poll {i+1}: status={doc['status']} chunks={doc['chunk_count']}")
            if doc["status"] == "ready":
                break
            if doc["status"] == "failed":
                print("INGEST FAILED:", doc["error_message"])
                return

        conv = (await client.post(f"{BASE}/knowledge-bases/{kb_id}/conversations", headers=headers, json={})).json()
        conv_id = conv["data"]["id"]

        chat = (
            await client.post(
                f"{BASE}/conversations/{conv_id}/chat",
                headers=headers,
                json={"question": "什么是RAG？请用2-3句话说明"},
            )
        ).json()
        print("\n=== ANSWER ===")
        print(chat["data"]["answer"])
        print(f"\nCitations: {len(chat['data']['citations'])}")
        for c in chat["data"]["citations"]:
            print(f"  [{c['index']}] {c['document_title']} score={c.get('score')}")
        print(f"Latency: {chat['data']['latency_ms']} ms")


if __name__ == "__main__":
    asyncio.run(main())
