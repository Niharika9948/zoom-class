import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [text, setText] = useState("");
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [txtFile, setTxtFile] = useState("");
  const [fileName, setFileName] = useState("");
  const notifiedTasks = useRef(new Set());

  // ✅ Clean task text
  const cleanTaskText = (text) => {
    return text
      .replace(/(tomorrow|today|by|before|on|due)/gi, "")
      .replace(/(please|you should|you have to|need to)/gi, "")
      .replace(/\band\b.*$/i, "")
      .replace(/\s+/g, " ")
      .trim();
  };

  // 🔔 Deadline checker (ALARM)
  const checkDeadlines = () => {
    const now = new Date();

    tasks.forEach((task) => {
      if (task.deadline && !task.completed) {
        const deadlineDate = new Date(task.deadline);
        const diffTime = deadlineDate - now;
        const diffDays = diffTime / (1000 * 60 * 60 * 24);

        if (diffDays <= 2) {
          if (!notifiedTasks.current.has(task._id)) {
            notifiedTasks.current.add(task._id);

            const audio = new Audio("/alert.mp3");

            let message =
              diffDays > 0
                ? `⏰ ${cleanTaskText(task.task)}`
                : `⚠️ ${cleanTaskText(task.task)} (Deadline Passed)`;

            audio.play()
              .then(() => {
                setTimeout(() => alert(message), 300);
              })
              .catch(() => alert(message));
          }
        }
      }
    });
  };

  useEffect(() => {
    checkDeadlines();
    const interval = setInterval(checkDeadlines, 60000);
    return () => clearInterval(interval);
  }, [tasks]);

  // ✅ Upload Audio Handler
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setFileName(file.name);

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);

    try {
      const res = await axios.post(
        "http://localhost:3001/upload",
        formData
      );

      console.log(res.data); // DEBUG

      setText(res.data.text || "");
      setTasks(res.data.tasks || []);
      setTxtFile(res.data.txt_file || "");
      notifiedTasks.current.clear();
    } catch (err) {
      console.error("Upload error:", err);
      alert("Upload failed!");
    } finally {
      setLoading(false);
    }
  };

  const downloadTxt = () => {
    const link = document.createElement("a");
    link.href = `http://127.0.0.1:8000/download/${txtFile}`;
    link.download = txtFile;
    link.click();
  };

  const markDone = async (task) => {
    try {
      await axios.post("http://127.0.0.1:8000/complete", {
        task: task.task,
      });

      setTasks((prev) =>
        prev.map((t) =>
          t._id === task._id ? { ...t, completed: true } : t
        )
      );
    } catch (err) {
      console.error("Error marking done:", err);
    }
  };

  return (
    <div className="app">
      <div className="card">
        <h1>🎙 Echo-Audit</h1>
        <p className="subtitle">
          Upload audio & auto-detect tasks
        </p>

        {/* ✅ Upload Box */}
        <label className="upload-box">
          <input
            type="file"
            accept="audio/*"
            onChange={handleFileUpload}
          />
          <div className="upload-content">
            📁 Click or Drag Audio File Here
          </div>
        </label>

        {fileName && <p className="file-name">📄 {fileName}</p>}

        {loading && (
          <p className="loading">Processing audio… ⏳</p>
        )}

        {text && (
          <>
            <div className="output">
              <h3>Transcript</h3>
              <p>{text}</p>
            </div>

            <button className="download" onClick={downloadTxt}>
              ⬇ Download Transcript
            </button>
          </>
        )}

        {/* ✅ TASKS (UNCHANGED) */}
        {tasks.length > 0 && (
          <div className="tasks">
            <h3>Tasks</h3>

            {tasks.map((t) => (
              <div
                key={t._id}
                className={`task ${t.completed ? "done" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={t.completed}
                  onChange={() => markDone(t)}
                />

                {cleanTaskText(t.task)}{" "}
                {t.deadline
                  ? `(Deadline: ${t.deadline})`
                  : ""}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;