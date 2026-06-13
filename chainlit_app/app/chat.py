# Chainlit chat handler — wired to the RAG backend.
import os
import httpx
import chainlit as cl

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:6100")


@cl.on_chat_start
async def start_chat():
    await cl.Message(
        content="👋 Hello! I'm your RAG assistant. Upload a PDF via the **Upload page** then ask me anything about it."
    ).send()


@cl.on_message
async def handle_message(message: cl.Message):
    async with cl.Step(name="Searching documents..."):
        pass

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{BACKEND_URL}/rag/query",
                json={"query": message.content},
            )
            response.raise_for_status()
            data = response.json()

        answer = data.get("answer", "No answer returned.")
        sources = data.get("sources", [])

        # Format sources as text elements
        source_text = ""
        if sources:
            source_text = "\n\n**Sources:**\n" + "\n".join([
                f"- [{i+1}] {int(s['similarity']*100)}% match — {s['content'][:120]}..."
                for i, s in enumerate(sources[:3])
            ])

        await cl.Message(content=answer + source_text).send()

    except Exception as e:
        await cl.Message(content=f"❌ Error: {str(e)}").send()
