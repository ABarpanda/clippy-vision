import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))



from contextlib import asynccontextmanager
import threading

from fastapi import FastAPI

from pydantic import BaseModel

from typing import Optional

import uvicorn, json

from fastapi.middleware.cors import CORSMiddleware



from agent.react_agent import run, run_stream, USER_MESSAGE_MAX_CHARS

from fastapi.responses import StreamingResponse
from fastapi import HTTPException

from core.storage import get_user_name, set_user_name

from core.memory_store import (

    get_identity,

    get_introduction,

    set_introduction,

    save_identity_field,

)

from core.intro_builder import start_intro_rebuild_daemon

from core.privacy_settings import list_privacy_targets, set_privacy_enabled

from agent.conversation import list_conversations, get_conversation_messages, search_conversations

from agent.router import load_classifier



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Weekly intro rebuild: immediate check + periodic background loop
    start_intro_rebuild_daemon()
    # Preload router classifier so the first chat does not pay the load cost
    threading.Thread(target=load_classifier, daemon=True, name="router-classifier-warmup").start()
    yield


app = FastAPI(lifespan=lifespan)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_methods=["*"],

    allow_headers=["*"],

)



class QueryRequest(BaseModel):

    message: str

    conversation_id: str



class NameRequest(BaseModel):

    name: str



class ProfileUpdateRequest(BaseModel):

    name: Optional[str] = None

    introduction: Optional[str] = None

    identity: Optional[dict[str, str]] = None



class PrivacyUpdateRequest(BaseModel):

    enabled: dict[str, bool]



def _validate_user_message(message: str) -> str:
    text = (message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(text) > USER_MESSAGE_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long ({len(text)} chars). Limit is {USER_MESSAGE_MAX_CHARS}.",
        )
    return text


@app.post("/chat")

def chat(req: QueryRequest):

    message = _validate_user_message(req.message)

    result = run(message, req.conversation_id)

    return {"result": result}



@app.post("/chat/stream")

def chat_stream(req: QueryRequest):

    message = _validate_user_message(req.message)

    def event_gen():

        try:

            for event in run_stream(message, req.conversation_id):

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        except Exception as e:

            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(

        event_gen(),

        media_type="text/event-stream",

        headers={

            "Cache-Control": "no-cache",

            "Connection": "keep-alive",

            "X-Accel-Buffering": "no",

        },

    )



@app.get("/user/name")

def read_user_name():

    return {"name": get_user_name()}



@app.post("/user/name")

def write_user_name(req: NameRequest):

    name = set_user_name(req.name)

    return {"name": name}



@app.get("/user/profile")

def read_user_profile():

    return {

        "name": get_user_name(),

        "introduction": get_introduction(),

        "identity": get_identity(),

    }



@app.post("/user/profile")

def write_user_profile(req: ProfileUpdateRequest):

    if req.name is not None:

        set_user_name(req.name)

    if req.introduction is not None:

        set_introduction(req.introduction.strip(), source="user")

    if req.identity:

        for field, value in req.identity.items():

            field = (field or "").strip().lower().replace(" ", "_")

            if not field:

                continue

            value = (value or "").strip()

            # User edits from Settings always win over agent/distiller values.

            save_identity_field(field, value=value, source="user", op="override")

    return {

        "name": get_user_name(),

        "introduction": get_introduction(),

        "identity": get_identity(),

    }



@app.get("/settings/privacy")

def read_privacy_settings():

    return {"targets": list_privacy_targets()}



@app.put("/settings/privacy")

def write_privacy_settings(req: PrivacyUpdateRequest):

    set_privacy_enabled(req.enabled)

    return {"targets": list_privacy_targets()}



@app.get("/conversations")

def conversations():

    return {"conversations": list_conversations()}



@app.get("/conversations/search")

def conversations_search(q: str = "", limit: int = 20):

    return {"conversations": search_conversations(q, limit=limit), "query": q}



@app.get("/conversations/{conversation_id}")

def conversation_messages(conversation_id: str):

    return {

        "conversation_id": conversation_id,

        "messages": get_conversation_messages(conversation_id),

    }



@app.get("/health")

def health():

    return {"status": "ok"}



if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)


