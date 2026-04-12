import os
import uuid
import shutil
import re

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pymongo import MongoClient

import whisper
import dateparser

# =========================
# APP SETUP
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_methods=["*"],
    allow_headers=["*"]
)

# =========================
# MONGO DB
# =========================
client = MongoClient(os.getenv("MONGO_URL"), serverSelectionTimeoutMS=5000)
db = client["echo_audit"]
tasks_collection = db["tasks"]

print("✅ MongoDB connected")

# =========================
# WHISPER MODEL
# =========================
model = None

@app.on_event("startup")
def load_model():
    global model
    print("🧠 Loading Whisper model...")
    model = whisper.load_model("base", device="cpu")
    print("✅ Whisper model loaded")

# =========================
# FILE STORAGE
# =========================
BASE_DIR = "/tmp"
os.makedirs(BASE_DIR, exist_ok=True)

# =========================
# TASK KEYWORDS
# =========================
TASK_KEYWORDS = [
    "write", "read", "revise", "note", "notes",
    "practice", "remember", "homework",
    "assignment", "finish", "complete", "project",
    "study", "prepare", "submit"
]

SENTENCE_REGEX = re.compile(r'[^.!?]+[.!?]?')

# =========================
# TRANSCRIPTION
# =========================
def transcribe_audio(path):
    global model
    if model is None:
        return {"text": "Model still loading. Try again in a few seconds."}

    result = model.transcribe(path, fp16=False)
    return result

# =========================
# TASK EXTRACTION (IMPROVED)
# =========================
def extract_tasks(text):
    tasks = []
    sentences = [s.strip() for s in SENTENCE_REGEX.findall(text) if s.strip()]

    for sentence in sentences:
        lower_sentence = sentence.lower()

        if any(kw in lower_sentence for kw in TASK_KEYWORDS):

            # deadline detection
            deadline = None
            date_match = re.search(r'\b(by|before|on|due)\s+(.+)', lower_sentence)

            if date_match:
                parsed = dateparser.parse(date_match.group(2))
                if parsed:
                    deadline = parsed.strftime("%Y-%m-%d %H:%M")

            task_data = {
                "task": sentence,
                "completed": False,
                "priority": "medium",
                "deadline": deadline
            }

            # avoid duplicates
            if not tasks_collection.find_one({"task": task_data["task"]}):
                inserted = tasks_collection.insert_one(task_data)
                task_data["_id"] = str(inserted.inserted_id)
                tasks.append(task_data)

    return tasks

# =========================
# MAIN API
# =========================
@app.post("/process")
async def process_audio(file: UploadFile = File(...)):

    print("📥 File received")

    audio_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".webm"

    audio_path = f"{BASE_DIR}/{audio_id}{ext}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    print("✅ Saved:", audio_path)

    try:
        print("🧠 Transcribing...")
        result = transcribe_audio(audio_path)
        text = result.get("text", "")
        print("🧠 Transcript:", text)

    except Exception as e:
        print("❌ Error:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

    # extract tasks
    tasks = extract_tasks(text)

    # save transcript
    txt_file = f"{audio_id}.txt"
    txt_path = f"{BASE_DIR}/{txt_file}"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {
        "success": True,
        "text": text,
        "tasks": tasks,
        "task_count": len(tasks),
        "txt_file": txt_file
    }

# =========================
# GET TASKS
# =========================
@app.get("/tasks")
def get_tasks():
    tasks = list(tasks_collection.find({}))
    for t in tasks:
        t["_id"] = str(t["_id"])
    return tasks

# =========================
# COMPLETE TASK
# =========================
@app.post("/complete")
def complete_task(task: dict):

    if "task" not in task:
        return {"error": "Missing task field"}

    tasks_collection.update_one(
        {"task": task["task"]},
        {"$set": {"completed": True}}
    )

    return {"status": "completed"}

# =========================
# DOWNLOAD TRANSCRIPT
# =========================
@app.get("/download/{filename}")
def download_file(filename: str):

    file_path = f"{BASE_DIR}/{filename}"

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})

    return FileResponse(file_path, media_type="text/plain", filename=filename)

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def home():
    return {
        "status": "running",
        "message": "AI Audio Transcription API is working"
    }