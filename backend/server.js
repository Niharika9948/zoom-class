const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
const path = require("path");
const cors = require("cors");
const mongoose = require("mongoose");
require("dotenv").config();

const app = express();

// -------------------- MongoDB --------------------
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log("✅ MongoDB Connected"))
  .catch((err) => console.error("❌ MongoDB error:", err));

// -------------------- Folders --------------------
const tempDir = "/tmp";   // ✅ IMPORTANT FOR RENDER
const savedDir = path.join(__dirname, "saved_audio");

if (!fs.existsSync(savedDir)) fs.mkdirSync(savedDir);

// -------------------- Multer --------------------
const upload = multer({ dest: tempDir });

// -------------------- Middleware --------------------
app.use(cors({
  origin: process.env.FRONTEND_URL || "*"
}));

app.use(express.json());

// -------------------- Upload Route --------------------
app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    console.log("📥 File received");

    if (!req.file) {
      console.log("❌ No file received");
      return res.status(400).json({ error: "No file received" });
    }

    const savedPath = path.join(savedDir, `recording_${Date.now()}.webm`);
    fs.renameSync(req.file.path, savedPath);

    console.log("✅ File saved at:", savedPath);

    const form = new FormData();
    form.append("file", fs.createReadStream(savedPath));

    console.log("🚀 Sending to AI service...");

    // 🔥 FIXED: Added /process
    const response = await axios.post(
      `${process.env.AI_SERVICE_URL}/process`,
      form,
      {
        headers: form.getHeaders(),
        maxBodyLength: Infinity,
      }
    );

    console.log("🧠 AI response received");

    res.json({
      text: response.data.text,
      tasks: response.data.tasks,
      audio_file: savedPath,
      txt_file: response.data.txt_file,
    });

  } catch (err) {
    console.error("❌ ERROR:", err.message);

    if (err.response) {
      console.error("❌ AI ERROR RESPONSE:", err.response.data);
    }

    res.status(500).json({
      error: "Processing failed",
      details: err.message
    });
  }
});

// -------------------- Health Route --------------------
app.get("/", (req, res) => {
  res.send("✅ Backend is running");
});

// -------------------- Start Server --------------------
const PORT = process.env.PORT || 10000;

app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
});