


const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
const path = require("path");
const cors = require("cors");
const mongoose = require("mongoose");

// MongoDB Connection
mongoose.connect("mongodb://127.0.0.1:27017/echo_audit")
  .then(() => console.log("✅ MongoDB Connected"))
  .catch((err) => console.error("❌ MongoDB connection error:", err));

const app = express();

const tempDir = path.join(__dirname, "temp");
const savedDir = path.join(__dirname, "saved_audio");

if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);
if (!fs.existsSync(savedDir)) fs.mkdirSync(savedDir);

const upload = multer({ dest: tempDir });

app.use(cors({ origin: "http://localhost:3000" }));

app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file received" });
    }

    // Save uploaded audio
    const savedPath = path.join(savedDir, `recording_${Date.now()}.webm`);
    fs.renameSync(req.file.path, savedPath);

    // Send file to FastAPI
    const form = new FormData();
    form.append("file", fs.createReadStream(savedPath));

    const response = await axios.post("http://127.0.0.1:8000/process", form, {
      headers: form.getHeaders(),
      maxBodyLength: Infinity,
    });

    res.json({
      text: response.data.text,
      tasks: response.data.tasks,
      audio_file: savedPath,
      txt_file: response.data.txt_file,
    });

  } catch (err) {
    console.error("Upload error:", err.message);
    res.status(500).json({ error: "Processing failed" });
  }
});

app.listen(3001, () => {
  console.log("✅ Node server running on http://localhost:3001");
});