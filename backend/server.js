const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
const path = require("path");
const cors = require("cors");
const mongoose = require("mongoose");
require("dotenv").config(); // ✅ load .env

const app = express();

// ✅ MongoDB Connection (Atlas)
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log("✅ MongoDB Connected"))
  .catch((err) => console.error("❌ MongoDB connection error:", err));

// ✅ Folders setup
const tempDir = path.join(__dirname, "temp");
const savedDir = path.join(__dirname, "saved_audio");

if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);
if (!fs.existsSync(savedDir)) fs.mkdirSync(savedDir);

// ✅ Multer config
const upload = multer({ dest: tempDir });

// ✅ CORS (allow frontend)
app.use(cors({
  origin: process.env.FRONTEND_URL || "*"
}));

app.use(express.json());

// ✅ Upload Route
app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file received" });
    }

    // Save uploaded audio
    const savedPath = path.join(savedDir, `recording_${Date.now()}.webm`);
    fs.renameSync(req.file.path, savedPath);

    // Send file to AI Service
    const form = new FormData();
    form.append("file", fs.createReadStream(savedPath));

    const response = await axios.post(
      process.env.AI_SERVICE_URL, // ✅ from .env
      form,
      {
        headers: form.getHeaders(),
        maxBodyLength: Infinity,
      }
    );

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

// ✅ Dynamic Port (important for deployment)
const PORT = process.env.PORT || 3001;

app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});