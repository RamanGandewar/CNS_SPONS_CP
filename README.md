# Deepfake Video Detection

Deepfake Video Detection is a Flask, React, and TensorFlow Lite web application for forensic video analysis. It samples frames from an uploaded or URL-based video, runs frame-level inference, and presents a dashboard with fake-probability timelines, suspicious timestamps, temporal consistency, performance metrics, and verdict interpretation.

The app now includes SQLite-backed signup/login so analysis access can be gated behind authenticated user sessions.

## Highlights

- React dashboard UI with plain CSS
- Top navigation layout instead of a left sidebar
- SQLite signup, login, logout, and session-backed auth
- Request tracing with `request_id` on production API responses
- Async analysis jobs with `job_id`, status polling, and result retrieval
- Input validation layer for file size, MP4/MOV container signature, duration, and readable frames
- Security headers, configurable CORS, and rate limiting hooks
- Prometheus-compatible `/metrics` endpoint
- Operator analytics dashboard in the React UI
- Health check endpoint for deployment probes
- Model metadata endpoint backed by `model/metadata.json`
- Video upload and URL input support
- TensorFlow Lite inference using `deepfake_detector_model_final.tflite`
- Per-frame fake probability scores returned to the frontend
- Chart.js frame timeline with red markers above the 70% suspicious threshold
- Temporal consistency analysis using score variance and standard deviation
- Processing metrics panel with timing, frame count, score stats, model name, and model version
- Verdict interpretation:
  - `0-30%`: Likely Real
  - `30-60%`: Uncertain
  - `60-85%`: Likely Deepfake
  - `85-100%`: Almost Certainly Deepfake
- REST API endpoint at `/api/analyze`
- Dockerfile and `docker-compose.yml` for reproducible deployment
- GitHub Actions CI workflow for linting, tests, and Docker build validation

## Tech Stack

- Python 3.13
- Flask 3.1.1
- SQLite
- TensorFlow 2.21.0
- TensorFlow Lite
- OpenCV
- NumPy
- React 18 via browser CDN
- Plain CSS
- Chart.js
- yt-dlp for URL video downloads
- Flask-CORS
- Flask-Limiter
- Docker / Docker Compose

## Application Flow

1. A user signs up or logs in from the React modal.
2. Flask stores the user in `data/deepfake_detector.sqlite3`.
3. The user uploads a video file or submits a public video URL.
4. The backend validates extension, file size, MP4/MOV magic bytes, duration, and readable frames.
5. `/api/v1/analyze` returns a `job_id` immediately.
6. The React app polls `/api/v1/status/<job_id>` until the job is complete.
7. The React app fetches `/api/v1/result/<job_id>`.
8. The backend records success/error metrics in SQLite.
9. The React dashboard renders the timeline graph, metrics, verdict, suspicious frames, admin analytics, and Grad-CAM availability status.
10. Temporary uploaded videos are deleted after processing.

## Authentication

Authentication is implemented in [app.py](./app.py) with SQLite and Werkzeug password hashing.

Available auth routes:

- `GET /api/auth/me`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`

Signup payload:

```json
{
  "name": "Analyst",
  "email": "analyst@example.com",
  "password": "password123"
}
```

Login payload:

```json
{
  "email": "analyst@example.com",
  "password": "password123"
}
```

The analysis endpoints require a signed-in session. Unauthenticated requests return:

```json
{
  "error": "Sign in before running an analysis."
}
```

## API Endpoints

### `GET /`

Returns the React-powered dashboard.

### `GET /health`

Returns service health for load balancers and deployment probes.

```json
{
  "status": "ok",
  "model_loaded": true,
  "uptime_seconds": 123.45,
  "version": "1.0.0",
  "model_version": "deepfake_detector_model_final.tflite"
}
```

### `GET /metrics`

Returns Prometheus-compatible operational metrics:

```text
frametruth_analyses_total 12
frametruth_errors_total 1
frametruth_average_confidence 0.72
frametruth_average_processing_seconds 1.42
```

### `GET /api/v1/model/info`

Returns model registry metadata from [model/metadata.json](./model/metadata.json).

### `GET /api/v1/admin/analytics`

Authenticated endpoint for operator analytics:

- total videos analyzed
- total errors and errors in the last hour
- verdict distribution
- average confidence
- average processing time
- recent analysis history
- system health

### `POST /api/v1/analyze`

Accepts either a video file or a URL.

Multipart upload example:

```powershell
curl -X POST http://127.0.0.1:5000/api/v1/analyze ^
  -b cookies.txt ^
  -F "video=@test/deepfake1.mp4"
```

URL example:

```json
{
  "url": "https://youtube.com/watch?v=example"
}
```

Immediate response:

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

### `GET /api/v1/status/<job_id>`

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

### `GET /api/v1/result/<job_id>`

Completed response shape:

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
    "frame_scores": [],
    "suspicious_markers": [],
    "consistency": {},
    "metrics": {},
    "artifacts": {}
  }
}
```

### `POST /api/analyze`

Compatibility route for older clients. This route still performs synchronous analysis and returns the same request-traced envelope:

```json
{
  "request_id": "a3f9c2d1-...",
  "status": "success",
  "data": {
    "deepfake_percentage": "72.73%"
  }
}
```

## Input Validation

The validation layer lives in [services/validator.py](./services/validator.py). It rejects files before inference when:

- the file is empty
- the file is larger than `MAX_UPLOAD_MB`, default `100`
- the container does not expose an MP4/MOV `ftyp` signature
- no readable frames are found
- duration is below 1 second
- duration is above `MAX_VIDEO_DURATION_SECONDS`, default `180`

## Observability

Operational data is stored in SQLite in the `analyses` table. The app tracks:

- total requests
- successful analyses
- failed analyses
- average model confidence
- average processing time
- verdict distribution
- errors in the last hour
- recent analysis history

The React admin dashboard reads this data from `/api/v1/admin/analytics`, while Prometheus or another scraper can read `/metrics`.

## Request Tracing

Each production API response includes:

```json
{
  "request_id": "a3f9c2d1-...",
  "status": "success",
  "data": {}
}
```

The same request id is also returned as the `X-Request-ID` response header.

## Security & Configuration

Security headers are added to every response:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy`
- `Permissions-Policy`
- `Content-Security-Policy`

Configuration can be supplied through environment variables. See [.env.example](./.env.example):

```text
SECRET_KEY=change-me-before-production
CORS_ORIGINS=http://127.0.0.1:5000,http://localhost:5000
MAX_UPLOAD_MB=100
MAX_VIDEO_DURATION_SECONDS=180
MAX_FRAMES=20
RATE_LIMIT_DEFAULT=100 per day
RATE_LIMIT_STORAGE_URI=memory://
LOG_LEVEL=INFO
```

## CI/CD

The GitHub Actions workflow in [.github/workflows/ci.yml](./.github/workflows/ci.yml) runs:

- dependency installation
- `ruff check .`
- `pytest -q`
- Docker image build validation

## Grad-CAM Status

The UI includes a Grad-CAM panel, but true Grad-CAM heatmaps require a Keras `.h5` or `.keras` model because TFLite does not expose intermediate convolutional layers. This repository currently ships only:

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
```

## Installation

### Recommended Windows Startup

```powershell
.\run.bat
```

Or skip dependency installation if the environment is already ready:

```powershell
.\run.ps1 -SkipInstall
```

### Manual Setup

```powershell
cd "C:\Users\HP\Desktop\SEM 6\CNS\CP-SPONSRED\Deepfake-video-detection-main"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Docker

Build and run with Docker Compose:

```powershell
docker compose up --build
```

The app will be available at:

```text
http://127.0.0.1:5000
```

## Dependencies

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

## Sample Test Data

The `test/` directory includes sample real and deepfake videos:

- `test/deepfake1.mp4`
- `test/deepfake2.mp4`
- `test/real1.mp4`
- `test/real2.mp4`
- `test/real3.mp4`

## Operational Notes

- Uploaded videos are temporary and deleted after inference.
- Generated suspicious-frame previews are written to `static/analysis/`.
- User accounts are stored locally in `data/deepfake_detector.sqlite3`.
- `data/`, `static/uploads/`, and `static/analysis/` are ignored by git.
- URL analysis requires `yt-dlp` and rejects videos longer than 3 minutes.
- React is loaded from a CDN in `templates/index.html`, so an internet connection is needed for the browser UI unless React is vendored locally.
- The Flask server is configured for local development when launched with `python app.py`.

## Limitations

- Grad-CAM is not fully implemented until a Keras `.h5` or `.keras` model is available.
- The current auth system is suitable for local/demo use; set a strong `SECRET_KEY` before production deployment.
- React currently runs via CDN/Babel for simplicity rather than a Vite or Webpack build.

## Future Improvements

- Add persistent analysis history per user
- Vendor React locally or add a Vite build for offline frontend development
- Implement Grad-CAM once a Keras model is available
- Add role-based admin permissions
- Add audit logs for auth and operator actions

## Useful Links

- Kaggle Dataset: [kaggle.com/datasets/reubensuju/celeb-df-v2](https://www.kaggle.com/datasets/reubensuju/celeb-df-v2)
- Dataset Used: [Google Drive Folder](https://drive.google.com/drive/folders/1ZwyawT2beV9pVDZlNePAq4pcagByWPmj?usp=sharing)
- Preprocessed Frames: [Google Drive Folder](https://drive.google.com/drive/folders/1bZBl5CgnfKwoial2eoUHwYlrxdwPyPHZ?usp=sharing)

## License

No explicit license file is currently included in the repository. Add a license if you plan to distribute or publish the project formally.
