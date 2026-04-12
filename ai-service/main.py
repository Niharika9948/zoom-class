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
    allow_origins=["*"],
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
# STORAGE
# =========================
BASE_DIR = "/tmp"
os.makedirs(BASE_DIR, exist_ok=True)

# =========================
# TASK KEYWORDS
# =========================
TASK_KEYWORDS = [
    "write", "read", "revise", "note", "notes",
    "practice", "remember", "homework",
    "assignment", "finish", "complete",
    "study", "prepare", "submit"
]

SENTENCE_REGEX = re.compile(r'[^.!?]+[.!?]?')

# =========================
# LOAD MODEL ONLY WHEN NEEDED (IMPORTANT FIX)
# =========================
model = None

def get_model():
    global model
    if model is None:
        print("🧠 Loading Whisper model (first request)...")
        model = whisper.load_model("tiny", device="cpu")
        print("✅ Model loaded")
    return model

# =========================
# TRANSCRIBE
# =========================
def transcribe_audio(path):
    model = get_model()
    result = model.transcribe(path, fp16=False)
    return result

# =========================
# TASK EXTRACTION
# =========================
def extract_tasks(text):
    tasks = []
    sentences = [s.strip() for s in SENTENCE_REGEX.findall(text) if s.strip()]

    for sentence in sentences:
        lower = sentence.lower()

        if any(kw in lower for kw in TASK_KEYWORDS):

            deadline = None
            match = re.search(r'\b(by|before|on|due)\s+(.+)', lower)

            if match:
                parsed = dateparser.parse(match.group(2))
                if parsed:
                    deadline = parsed.strftime("%Y-%m-%d %H:%M")

            task_data = {
                "task": sentence,
                "completed": False,
                "priority": "medium",
                "deadline": deadline
            }

            if not tasks_collection.find_one({"task": sentence}):
                inserted = tasks_collection.insert_one(task_data)
                task_data["_id"] = str(inserted.inserted_id)
                tasks.append(task_data)

    return tasks

# =========================
# MAIN API
# =========================
@app.post("/process")
async def process_audio(file: UploadFile = File(...)):

    audio_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".webm"
    audio_path = f"{BASE_DIR}/{audio_id}{ext}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = transcribe_audio(audio_path)
        text = result["text"]

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    tasks = extract_tasks(text)

    txt_file = f"{audio_id}.txt"
    txt_path = f"{BASE_DIR}/{txt_file}"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {
        "text": text,
        "tasks": tasks,
        "task_count": len(tasks),
        "txt_file": txt_file
    }

# =========================
# TASKS API
# =========================
@app.get("/tasks")
def get_tasks():
    tasks = list(tasks_collection.find({}))
    for t in tasks:
        t["_id"] = str(t["_id"])
    return tasks

@app.post("/complete")
def complete_task(task: dict):
    tasks_collection.update_one(
        {"task": task["task"]},
        {"$set": {"completed": True}}
    )
    return {"status": "ok"}

# =========================
# DOWNLOAD
# =========================
@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = f"{BASE_DIR}/{filename}"

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "Not found"})

    return FileResponse(file_path, media_type="text/plain", filename=filename)

# =========================
# HEALTH
# =========================
@app.get("/")
def home():
    return {"status": "running"}