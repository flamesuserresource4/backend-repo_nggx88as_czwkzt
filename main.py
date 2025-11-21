import os
import re
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import create_document, get_documents

app = FastAPI(title="Ayan Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Ayan Portfolio Backend Running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ---------------------------
# Guestbook API
# ---------------------------

URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class GuestbookCreate(BaseModel):
    name: str = Field(..., max_length=80)
    message: str = Field(..., max_length=500, description="Emojis allowed; links are stripped for safety")


class GuestbookEntry(BaseModel):
    _id: str
    name: str
    message: str
    created_at: datetime


@app.get("/guestbook", response_model=List[GuestbookEntry])
def list_guestbook(limit: int = 50):
    try:
        docs = get_documents("guestbook", {}, limit=limit)
        # Sort by created_at desc if field exists
        docs.sort(key=lambda d: d.get("created_at", datetime.min), reverse=True)
        # Convert ObjectId to str if present
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/guestbook", response_model=GuestbookEntry)
def add_guestbook(payload: GuestbookCreate):
    name = payload.name.strip()
    message = payload.message.strip()

    if not name or not message:
        raise HTTPException(status_code=400, detail="Name and message are required")

    # Strip links for safety, but keep emojis and text
    message_sanitized = URL_REGEX.sub("[link removed]", message)

    data = {"name": name, "message": message_sanitized}

    try:
        inserted_id = create_document("guestbook", data)
        # Fetch the inserted document shape for response
        created_at = datetime.now().isoformat()
        # create_document adds created_at/updated_at server-side; we mirror here
        return {
            "_id": inserted_id,
            "name": name,
            "message": message_sanitized,
            "created_at": datetime.now(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
