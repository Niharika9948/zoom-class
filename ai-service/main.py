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
# FASTAPI SETUP
# =========================
app = FastAPI()

# ✅ FINAL CORS (secure + working)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_methods=["*"],
    allow_headers=["*"]
)

# =========================
# MONGODB
# =========================
client = MongoClient(os.getenv("MONGO_URL"))
db = client["echo_audit"]
tasks_collection = db["tasks"]

# =========================
# WHISPER (LOAD ONCE ONLY)
# =========================
model = None

def get_model():
    global model
    if model is None:
        print("🧠 Loading Whisper model...")
        model = whisper.load_model("tiny", device="cpu")
        print("✅ Model loaded")
    return model


def transcribe_audio(path):
    m = get_model()
    result = m.transcribe(path, fp16=False)
    return result

# =========================
# FOLDER SETUP
# =========================
os.makedirs("recordings", exist_ok=True)

# =========================
# TASK KEYWORDS
# =========================
TASK_KEYWORDS = [
    "write", "read", "revise", "note", "notes",
    "practice", "remember", "homework",
    "assignment", "finish", "complete", "project"
]

SENTENCE_REGEX = re.compile(r'[^.!?]+[.!?]?')

# =========================
# TASK EXTRACTION
# =========================
def extract_tasks(text):
    tasks = []
    sentences = [s.strip() for s in SENTENCE_REGEX.findall(text) if s.strip()]

    for sentence in sentences:
        words = sentence.lower().split()

        if any(kw in words for kw in TASK_KEYWORDS):

            deadline = None

            date_match = re.search(r'\b(by|before|on|due)\s+(.+)', sentence.lower())
            if date_match:
                parsed = dateparser.parse(date_match.group(2))
                if parsed:
                    deadline = parsed.strftime("%Y-%m-%d %H:%M")

            task_data = {
                "task": sentence.strip(),
                "completed": False,
                "priority": "medium",
                "deadline": deadline
            }

            if not tasks_collection.find_one({"task": task_data["task"]}):
                inserted = tasks_collection.insert_one(task_data)
                task_data["_id"] = str(inserted.inserted_id)
                tasks.append(task_data)

    return tasks

# =========================
# AUDIO PROCESSING
# =========================
@app.post("/process")
async def process_audio(file: UploadFile = File(...)):

    print("📥 Received file")

    audio_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".webm"
    audio_path = f"recordings/{audio_id}{ext}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    print("✅ File saved:", audio_path)

    try:
        print("🧠 Transcribing...")
        result = transcribe_audio(audio_path)
        text = result.get("text", "")
        print("🧠 Text:", text)

    except Exception as e:
        print("❌ ERROR:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

    tasks = extract_tasks(text)
    print("📋 Tasks:", tasks)

    txt_file = f"{audio_id}.txt"
    txt_path = os.path.join("recordings", txt_file)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {
        "text": text,
        "tasks": tasks,
        "txt_file": txt_file
    }

# =========================
# TASK APIs
# =========================
@app.get("/tasks")
def get_tasks():
    all_tasks = list(tasks_collection.find({}))
    for t in all_tasks:
        t["_id"] = str(t["_id"])
    return all_tasks


@app.post("/complete")
def complete_task(task: dict):
    if "task" not in task:
        return {"error": "Missing 'task' key"}

    tasks_collection.update_one(
        {"task": task["task"]},
        {"$set": {"completed": True}}
    )

    return {"status": "done"}

# =========================
# DOWNLOAD TRANSCRIPT
# =========================
@app.get("/download/{filename}")
def download_txt(filename: str):
    file_path = os.path.join("recordings", filename)

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})

    return FileResponse(file_path, media_type="text/plain", filename=filename)