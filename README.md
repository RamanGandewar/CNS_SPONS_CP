<div align="center">

<img src="static/img/logo.jpeg" alt="FrameTruth Logo" width="120" height="120" style="border-radius: 16px;" />

# 🎭 FrameTruth — Deepfake Video Detection

**Forensic-grade AI video analysis. Built for truth.**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.21.0-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)](https://tensorflow.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![SQLite](https://img.shields.io/badge/SQLite-Backed-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<<<<<<< HEAD
<br/>
=======
## Architecture

![System Architecture](./images/SYS_ARCH.png)

## Tech Stack
>>>>>>> 9380e42 (Updated README and added images)

> **FrameTruth** samples frames from any uploaded or URL-sourced video, runs per-frame TFLite inference,
> and returns a rich forensic dashboard — timeline charts, suspicious timestamps, temporal consistency scores,
> performance metrics, and a human-readable verdict. All behind secure, session-gated authentication.

<<<<<<< HEAD
<br/>

[🚀 Quick Start](#-quick-start) • [📐 Architecture](#-architecture) • [🔌 API Reference](#-api-reference) • [🐳 Docker](#-docker-deployment) • [📊 Dashboard](#-dashboard--analytics) • [🛡️ Security](#%EF%B8%8F-security) • [🗺️ Roadmap](#%EF%B8%8F-roadmap)
=======
## User Flow

![User Flow](./images/USERFLOW.png)
>>>>>>> 9380e42 (Updated README and added images)

---

</div>

## ✨ What Makes This Different

| Feature | Description |
|---|---|
| 🧠 **TFLite Inference** | Fast, lightweight frame-level deepfake scoring with no GPU required |
| 📈 **Timeline Analysis** | Chart.js frame-by-frame probability graph with red suspicious-frame markers |
| ⏱️ **Temporal Consistency** | Variance + standard deviation analysis across frames — not just an average score |
| 🔐 **Auth-Gated Access** | SQLite-backed signup/login with Werkzeug password hashing |
| 🆔 **Async Job Queue** | Submit → get `job_id` → poll → retrieve. Non-blocking by design |
| 📡 **Request Tracing** | Every API response carries a `request_id` and `X-Request-ID` header |
| 📊 **Operator Analytics** | Built-in admin dashboard for verdict distribution, error rates, and history |
| 🧪 **Prometheus Metrics** | `/metrics` endpoint ready for Grafana / alerting pipelines |
| 🛡️ **Input Validation** | Magic-byte container check, duration limits, frame readability — before inference |
| 🌐 **URL Video Support** | `yt-dlp` integration for public video URLs (≤ 3 min) |

---

## 🖥️ Dashboard & Analytics

The React dashboard (served at `/`) gives analysts a complete picture at a glance:

```
┌─────────────────────────────────────────────────────────┐
│  🎭 FrameTruth          [Login]  [Upload]  [Analytics]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  VERDICT: ⚠️  Likely Deepfake   (72.73%)               │
│                                                         │
│  Frame Timeline ─────────────────────────────────────── │
│  1.0 │         ████  ██                                 │
│  0.7 │ ──────threshold──────────────────────────────── │
│  0.0 └──────────────────────────────────────────────── │
│       Frame 1        Frame 10        Frame 20           │
│                                                         │
│  Suspicious Frames: [#4] [#7] [#12]                     │
│  Temporal Consistency: ⚠️  High Variance (σ = 0.31)    │
│                                                         │
│  Processing Time: 1.42s  │  Frames Analysed: 20        │
│  Model: deepfake_detector_model_final.tflite  v1.0.0   │
│                                                         │
│  📊 Admin Analytics   🔬 Grad-CAM Status               │
└─────────────────────────────────────────────────────────┘
```

**Verdict Scale:**

| Score | Label | Tone |
|---|---|---|
| `0 – 30%` | ✅ Likely Real | Safe |
| `30 – 60%` | 🟡 Uncertain | Caution |
| `60 – 85%` | ⚠️ Likely Deepfake | Warning |
| `85 – 100%` | 🚨 Almost Certainly Deepfake | Critical |

---

## 📐 Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                            BROWSER (React 18)                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Auth Modal  │  │ Upload / URL │  │ Frame Chart  │  │  Admin Tab │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
└─────────┼────────────────┼─────────────────┼────────────────┼─────────┘
          │                │                 │                │
          ▼                ▼                 ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLASK 3.1 (app.py)                              │
│                                                                         │
│  /api/auth/*   /api/v1/analyze   /api/v1/status   /api/v1/result       │
│  /api/v1/admin/analytics         /metrics         /health              │
│                                                                         │
│  ┌──────────────┐   ┌─────────────────┐   ┌──────────────────────┐    │
│  │  Auth Layer  │   │ Validator Layer  │   │  Async Job Manager   │    │
│  │  (SQLite +   │   │ (services/       │   │  (job_id → thread)   │    │
│  │  Werkzeug)   │   │  validator.py)   │   │                      │    │
│  └──────────────┘   └────────┬────────┘   └──────────┬───────────┘    │
│                              │                        │                 │
│                    ┌─────────▼────────────────────────▼──────────┐     │
│                    │          utils/video_processing.py           │     │
│                    │   OpenCV frame sampling → TFLite inference   │     │
│                    │   → score aggregation → consistency stats    │     │
│                    └──────────────────────────────────────────────┘     │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │            SQLite  (data/deepfake_detector.sqlite3)               │  │
│  │  users · analyses · metrics · error_log                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          │                             │
          ▼                             ▼
   model/*.tflite                static/analysis/
   (TFLite graphs)               (frame previews)
```

### Application Flow

```
1. User signs up / logs in          → Flask stores hashed password in SQLite
2. User submits video / URL         → Validator checks size, magic bytes, duration, frames
3. POST /api/v1/analyze             → Returns job_id immediately (non-blocking)
4. React polls /api/v1/status/:id   → Until status == "complete"
5. React fetches /api/v1/result/:id → Full analysis payload
6. Dashboard renders                → Timeline, verdict, suspicious frames, metrics
7. SQLite records result            → Feeds /metrics and /api/v1/admin/analytics
8. Temp upload deleted              → No video retained after inference
```

---

## 🚀 Quick Start

### ⚡ Windows (Recommended)

```bat
.\run.bat
```

Or skip reinstallation if dependencies are already present:

```powershell
.\run.ps1 -SkipInstall
```

### 🐍 Manual Setup (Any OS)

```bash
# 1. Clone and enter the project
git clone https://github.com/your-username/deepfake-video-detection.git
cd deepfake-video-detection

# 2. Create and activate a virtual environment
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.\.venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Copy and configure environment variables
cp .env.example .env

# 5. Start the server
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🐳 Docker Deployment

```bash
# Build and start with Docker Compose
docker compose up --build

# Run detached
docker compose up -d --build

# Tear down
docker compose down
```

The app will be available at **http://127.0.0.1:5000**

> **Tip:** Set `SECRET_KEY` in your `.env` or as a Docker secret before any production deployment.

---

## ⚙️ Configuration

All settings are configurable via environment variables. Copy `.env.example` to `.env`:

```env
# Security
SECRET_KEY=change-me-before-production

# CORS
CORS_ORIGINS=http://127.0.0.1:5000,http://localhost:5000

# Upload limits
MAX_UPLOAD_MB=100
MAX_VIDEO_DURATION_SECONDS=180
MAX_FRAMES=20

# Rate limiting
RATE_LIMIT_DEFAULT=100 per day
RATE_LIMIT_STORAGE_URI=memory://

# Logging
LOG_LEVEL=INFO
```

---

## 🔌 API Reference

All production API responses share a common envelope:

```json
{
  "request_id": "a3f9c2d1-...",
  "status": "success",
  "data": { }
}
```

The same `request_id` is also returned in the `X-Request-ID` response header for log correlation.

---

### 🔐 Authentication

#### `POST /api/auth/signup`

```json
{
  "name": "Analyst",
  "email": "analyst@example.com",
  "password": "password123"
}
```

#### `POST /api/auth/login`

```json
{
  "email": "analyst@example.com",
  "password": "password123"
}
```

#### `POST /api/auth/logout`
#### `GET /api/auth/me`

> Protected analysis endpoints return `401` with `"error": "Sign in before running an analysis."` if unauthenticated.

---

### 🎬 Video Analysis

#### `POST /api/v1/analyze`

Upload a file:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/analyze \
  -b cookies.txt \
  -F "video=@test/deepfake1.mp4"
```

Or submit a public URL:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/analyze \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=example"}'
```

**Immediate response:**

```json
{
  "request_id": "a3f9c2d1-...",
  "status": "success",
  "data": {
    "job_id": "81c37ee5-...",
    "status": "processing",
    "progress": 10,
    "poll_url": "/api/v1/status/81c37ee5-...",
    "result_url": "/api/v1/result/81c37ee5-..."
  }
}
```

#### `GET /api/v1/status/<job_id>`

```json
{
  "request_id": "a3f9c2d1-...",
  "status": "success",
  "data": {
    "job_id": "81c37ee5-...",
    "status": "complete",
    "progress": 100
  }
}
```

#### `GET /api/v1/result/<job_id>`

```json
{
  "request_id": "a3f9c2d1-...",
  "status": "success",
  "data": {
    "job_id": "81c37ee5-...",
    "analysis_id": "abc123",
    "source_type": "upload",
    "deepfake_score": 0.7272,
    "deepfake_percentage": "72.73%",
    "verdict": {
      "label": "Likely Deepfake",
      "tone": "fake"
    },
    "frame_scores": [0.12, 0.89, 0.74, "..."],
    "suspicious_markers": [4, 7, 12],
    "consistency": {
      "variance": 0.096,
      "std_dev": 0.310
    },
    "metrics": {
      "processing_time_seconds": 1.42,
      "frame_count": 20,
      "model_name": "deepfake_detector_model_final.tflite",
      "model_version": "1.0.0"
    },
    "artifacts": { }
  }
}
```

---

### 📊 Observability & Admin

#### `GET /health`

```json
{
  "status": "ok",
  "model_loaded": true,
  "uptime_seconds": 123.45,
  "version": "1.0.0",
  "model_version": "deepfake_detector_model_final.tflite"
}
```

#### `GET /metrics` — Prometheus-compatible

```
frametruth_analyses_total 12
frametruth_errors_total 1
frametruth_average_confidence 0.72
frametruth_average_processing_seconds 1.42
```

#### `GET /api/v1/admin/analytics` *(authenticated)*

Returns verdict distribution, error rates, average confidence, processing time, and recent history.

#### `GET /api/v1/model/info`

Returns model registry metadata from `model/metadata.json`.

#### `POST /api/analyze` *(legacy)*

Synchronous compatibility route for older clients. Returns the same traced envelope.

---

## 🛡️ Security

Every response includes hardened security headers:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Restrictive |
| `Content-Security-Policy` | Configured |

Additional protections:
- **Werkzeug password hashing** — no plaintext passwords stored
- **Configurable CORS** — allowlist via `CORS_ORIGINS`
- **Rate limiting** — Flask-Limiter with configurable backend
- **Temp file cleanup** — uploaded videos deleted immediately after inference
- **Input validation** — magic-byte container check, file size cap, duration limit, frame readability check

---

## ✅ Input Validation

The validation layer (`services/validator.py`) rejects videos **before inference** when:

- File is empty or missing
- File exceeds `MAX_UPLOAD_MB` (default: `100 MB`)
- Container does not have a valid MP4/MOV `ftyp` magic byte signature
- No readable frames are found by OpenCV
- Duration is below `1 second`
- Duration exceeds `MAX_VIDEO_DURATION_SECONDS` (default: `180 s`)

---

## 🧪 Testing

```bash
# Run the test suite
pytest -q

# Lint with ruff
ruff check .
```

Sample test videos are included in `test/`:

| File | Type |
|---|---|
| `test/deepfake1.mp4` | Deepfake |
| `test/deepfake2.mp4` | Deepfake |
| `test/real1.mp4` | Authentic |
| `test/real2.mp4` | Authentic |
| `test/real3.mp4` | Authentic |

---

## 🔁 CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request:

<<<<<<< HEAD
```
✔ pip install -r requirements.txt
✔ ruff check .
✔ pytest -q
✔ docker build validation
=======
- `model/deepfake_detector_model_final.tflite`
- `model/deepfake_detector_model4.tflite`

When a compatible Keras model is added, the backend can be extended to generate overlays for the most suspicious frames.

## Project Structure

```text
Deepfake-video-detection-main/
|-- app.py
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- runtime.txt
|-- run.ps1
|-- run.bat
|-- README.md
|-- CHANGELOG.md
|-- .env.example
|-- images/
|   |-- SYS_ARCH.png
|   `-- USERFLOW.png
|-- .github/
|   `-- workflows/
|       `-- ci.yml
|-- data/
|   `-- deepfake_detector.sqlite3        # generated locally
|-- model/
|   |-- deepfake_detector_model_final.tflite
|   |-- deepfake_detector_model4.tflite
|   `-- metadata.json
|-- services/
|   |-- __init__.py
|   `-- validator.py
|-- static/
|   |-- analysis/                        # generated frame previews
|   |-- css/
|   |   `-- styles.css
|   |-- img/
|   |   `-- logo.jpeg
|   |-- js/
|   |   `-- script.js                    # React app
|   `-- uploads/                         # temporary uploads
|-- templates/
|   `-- index.html                       # React mount point
|-- test/
|   |-- deepfake1.mp4
|   |-- deepfake2.mp4
|   |-- real1.mp4
|   |-- real2.mp4
|   `-- real3.mp4
|-- tests/
|   `-- test_api_contract.py
`-- utils/
    `-- video_processing.py
>>>>>>> 9380e42 (Updated README and added images)
```

---

## 📁 Project Structure

```
deepfake-video-detection/
├── app.py                          # Flask app, routes, auth, job manager
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── runtime.txt
├── run.bat / run.ps1               # Windows convenience launchers
├── .env.example
│
├── .github/
│   └── workflows/ci.yml           # GitHub Actions CI
│
├── data/
│   └── deepfake_detector.sqlite3  # Generated at runtime (gitignored)
│
├── model/
│   ├── deepfake_detector_model_final.tflite   # Primary model
│   ├── deepfake_detector_model4.tflite        # Alternate model
│   └── metadata.json
│
├── services/
│   ├── __init__.py
│   └── validator.py               # Input validation layer
│
├── static/
│   ├── analysis/                  # Generated frame previews (gitignored)
│   ├── css/styles.css
│   ├── img/logo.jpeg
│   ├── js/script.js               # React app (Babel CDN)
│   └── uploads/                   # Temporary uploads (gitignored)
│
├── templates/
│   └── index.html                 # React mount point
│
├── test/                          # Sample videos for manual testing
│
├── tests/
│   └── test_api_contract.py
│
└── utils/
    └── video_processing.py        # OpenCV + TFLite frame pipeline
```

---

## 🔬 Grad-CAM Status

The dashboard includes a **Grad-CAM panel** to surface which spatial regions triggered the model. However, true Grad-CAM heatmaps require intermediate convolutional layer access — which TFLite does not expose.

**Current model files:**
- `model/deepfake_detector_model_final.tflite` ✅ (in use)
- `model/deepfake_detector_model4.tflite` ✅ (alternate)

**To enable Grad-CAM:** Add a Keras `.h5` or `.keras` model. The backend is structured to accept an extension at `utils/video_processing.py`.

---

## 🗺️ Roadmap

- [ ] Grad-CAM heatmap overlays (requires Keras model)
- [ ] Per-user persistent analysis history
- [ ] Role-based admin permissions (analyst / operator / superadmin)
- [ ] Vendor React locally (Vite build) for offline-capable frontend
- [ ] Audit log for auth and operator actions
- [ ] Exportable forensic PDF report per analysis
- [ ] WebSocket-based real-time progress (replace polling)
- [ ] Multi-model ensemble scoring

---

## 📦 Dependencies

```text
flask==3.1.1
numpy>=1.26,<2.2
opencv-python>=4.10,<5
tensorflow==2.21.0
yt-dlp>=2025.1.15
gunicorn>=23.0,<24
flask-cors>=5.0,<6
flask-limiter>=3.8,<4
python-dotenv>=1.0,<2
pytest>=8.0,<9
ruff>=0.8,<1
```

---

## 🔗 Dataset & Resources

| Resource | Link |
|---|---|
| Kaggle Dataset (Celeb-DF v2) | [kaggle.com/datasets/reubensuju/celeb-df-v2](https://www.kaggle.com/datasets/reubensuju/celeb-df-v2) |
| Raw Dataset (Google Drive) | [Drive Folder](https://drive.google.com/drive/folders/1ZwyawT2beV9pVDZlNePAq4pcagByWPmj?usp=sharing) |
| Preprocessed Frames | [Drive Folder](https://drive.google.com/drive/folders/1bZBl5CgnfKwoial2eoUHwYlrxdwPyPHZ?usp=sharing) |
| Flask Docs | [flask.palletsprojects.com](https://flask.palletsprojects.com) |
| TensorFlow Lite | [tensorflow.org/lite](https://www.tensorflow.org/lite) |

---

## ⚠️ Operational Notes

- Uploaded videos are **deleted immediately** after inference — nothing is retained.
- Frame preview images are written to `static/analysis/` (gitignored).
- User accounts live in `data/deepfake_detector.sqlite3` (gitignored).
- React is served via CDN + Babel — an internet connection is needed for the browser UI unless React is vendored locally.
- URL analysis uses `yt-dlp` and rejects videos longer than **3 minutes**.
- The built-in Flask dev server (`python app.py`) is for **local development only**. Use `gunicorn` via Docker for production.

---

## 📜 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---
