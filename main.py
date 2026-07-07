import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import GEMINI_MODEL
from llm import LLMError, get_response_stream

app = FastAPI()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[Message]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _stream_chat(history: list[dict]) -> Iterator[str]:
    try:
        for delta in get_response_stream(history):
            yield _sse({"delta": delta})
        yield _sse({"done": True})
    except LLMError as exc:
        yield _sse({"error": str(exc)})


@app.post("/chat")
def chat(request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return StreamingResponse(_stream_chat(history), media_type="text/event-stream")


@app.get("/model-info")
def model_info():
    return {"model": GEMINI_MODEL}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
