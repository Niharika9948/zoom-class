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
  .then(() => console.log("MongoDB Connected"))
  .catch((err) => console.error("MongoDB error:", err));

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
    if (!req.file) {
      return res.status(400).json({ error: "No file received" });
    }

    const savedPath = path.join(savedDir, `recording_${Date.now()}.webm`);
    fs.renameSync(req.file.path, savedPath);

    const form = new FormData();
    form.append("file", fs.createReadStream(savedPath));

    const response = await axios.post(
      process.env.AI_SERVICE_URL,
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
    console.error(err);
    res.status(500).json({ error: "Processing failed" });
  }
});

// -------------------- Health Route --------------------
app.get("/", (req, res) => {
  res.send("Backend is running");
});

// -------------------- Start Server --------------------
const PORT = process.env.PORT || 10000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});