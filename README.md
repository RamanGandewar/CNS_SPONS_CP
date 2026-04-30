# FrameTruth AI

FrameTruth AI is a Flask and React deepfake forensics platform for video analysis. It combines frame-level TFLite inference with an ensemble scoring layer, forensic secondary signals, operator analytics, JWT auth, audit logging, and exportable PDF reporting.

## Highlights

- JWT-based auth with role-aware access for `analyst`, `operator`, and `admin`
- Structured JSON logging with `request_id`, `job_id`, `user_id`, `duration_ms`, and `verdict`
- Async analysis jobs with `job_id`, polling, and result retrieval
- Prometheus-compatible `/metrics`
- Operator analytics dashboard plus Grafana provisioning assets
- Improved `/health` with DB, Redis, and Celery status
- Ensemble inference across both bundled TFLite models
- Frequency-domain analysis, optical-flow consistency, facial landmark displacement fallback, and audio-visual sync proxy
- Exportable forensic PDF report per completed analysis
- Notebook code exported into `notebooks_converted/`

## Implemented Upgrade Set

The current codebase now covers the full 12-item upgrade track we discussed:

1. Structured JSON logging
2. Stronger health checks and metrics
3. Grafana dashboard provisioning
4. Audit logging plus role-based access control
5. Exportable forensic PDF reporting
6. Frequency analysis and optical-flow scoring
7. Facial landmark displacement analysis
8. Grad-CAM support for future Keras models
9. Multi-model ensemble scoring plus calibration metadata
10. Celery, Redis, and OpenTelemetry production hooks
11. JWT-based authentication
12. Audio-visual sync proxy analysis

## Architecture

![System Architecture](./images/SYS_ARCH.png)

## User Flow

![User Flow](./images/USERFLOW.png)

## Tech Stack

- Python 3.13
- Flask 3.1
- React 18
- TensorFlow Lite
- OpenCV
- SQLite
- JWT
- Prometheus / Grafana
- Docker Compose

## API

`POST /api/auth/signup`

Creates a user. The very first account created in a fresh database is assigned the `admin` role automatically.

`POST /api/auth/login`

Returns an `access_token` plus user profile.

`GET /api/auth/me`

Returns the current JWT-authenticated user.

`POST /api/v1/analyze`

Queues an async analysis job and returns:

```json
{
  "request_id": "uuid",
  "status": "success",
  "data": {
    "job_id": "uuid",
    "status": "processing",
    "poll_url": "/api/v1/status/<job_id>",
    "result_url": "/api/v1/result/<job_id>"
  }
}
```

`GET /api/v1/status/<job_id>`

Returns job progress and failure details if present.

`GET /api/v1/result/<job_id>`

Returns the completed analysis payload including:

- verdict and confidence
- frame scores and suspicious markers
- ensemble disagreement
- frequency analysis
- optical-flow consistency
- landmark displacement fallback
- audio-visual sync proxy
- report URL

`GET /api/v1/report/<analysis_id>`

Downloads the generated forensic PDF.

`GET /api/v1/admin/analytics`

Operator/admin analytics including totals, verdict distribution, latency percentiles, and recent history.

`GET /api/v1/model/info`

Returns the model registry and calibration metadata.

`GET /health`

Returns uptime, DB ping, Redis reachability, Celery mode, and loaded model count.

`GET /metrics`

Exposes Prometheus metrics such as:

```text
frametruth_analyses_total
frametruth_errors_total
frametruth_average_confidence
frametruth_latency_p50_seconds
frametruth_latency_p95_seconds
frametruth_latency_p99_seconds
frametruth_verdict_total{verdict="Likely Deepfake"}
```

## Reliability And Observability

- Structured JSON logging is configured in [services/logging_utils.py](./services/logging_utils.py)
- OpenTelemetry span hooks are available in [services/tracing.py](./services/tracing.py)
- Grafana and Prometheus provisioning live under `monitoring/`
- Audit records are stored in the SQLite `audit_log` table
- Role-restricted admin endpoints are enforced by JWT claims

## Forensic Signals

The analysis pipeline now adds multiple signals beyond the base classifier:

- Ensemble deepfake score from both TFLite models
- Frequency-domain artifact score using FFT energy distribution
- Optical-flow consistency using Farneback motion fields
- Facial landmark displacement fallback using Haar face detection plus Shi-Tomasi feature tracking
- Audio-visual sync proxy using extracted audio RMS versus lower-face motion
- Grad-CAM support when a `.keras` or `.h5` model is added

The Grad-CAM implementation is present in [services/explainability.py](./services/explainability.py), but it only activates when a Keras model is available in `model/`.

## Notebook Conversion

The runtime app does not depend on Jupyter notebooks. The original experiment notebooks are still in the repo for reference, and their code was also exported into Python scripts for easier review and reuse:

- [CSI_0.py](./notebooks_converted/CSI_0.py)
- [CSI_1.py](./notebooks_converted/CSI_1.py)
- [CSI_3.py](./notebooks_converted/CSI_3.py)
- [CSI_4.py](./notebooks_converted/CSI_4.py)

## Project Structure

```text
Deepfake-video-detection-main/
|-- app.py
|-- CHANGELOG.md
|-- Dockerfile
|-- docker-compose.yml
|-- README.md
|-- requirements.txt
|-- images/
|   |-- SYS_ARCH.png
|   `-- USERFLOW.png
|-- model/
|   |-- calibration.json
|   |-- deepfake_detector_model4.tflite
|   |-- deepfake_detector_model_final.tflite
|   `-- metadata.json
|-- monitoring/
|   |-- prometheus.yml
|   `-- grafana/
|-- notebooks_converted/
|   |-- CSI_0.py
|   |-- CSI_1.py
|   |-- CSI_3.py
|   `-- CSI_4.py
|-- services/
|   |-- auth.py
|   |-- explainability.py
|   |-- forensics.py
|   |-- logging_utils.py
|   |-- pdf_report.py
|   |-- tracing.py
|   `-- validator.py
|-- static/
|   |-- analysis/
|   |-- css/
|   |-- img/
|   |-- js/
|   |-- reports/
|   `-- uploads/
|-- templates/
|   `-- index.html
|-- tests/
|   `-- test_api_contract.py
`-- utils/
    `-- video_processing.py
```

## Setup

Windows quick start:

```powershell
.\run.bat
```

Manual setup:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Docker And Monitoring

Run the app plus Redis, Prometheus, and Grafana:

```powershell
docker compose up --build
```

Ports:

- app: `5000`
- Redis: `6379`
- Prometheus: `9090`
- Grafana: `3000`

## Config

Copy [.env.example](./.env.example) to `.env` and adjust values such as:

- `SECRET_KEY`
- `CORS_ORIGINS`
- `MAX_UPLOAD_MB`
- `MAX_VIDEO_DURATION_SECONDS`
- `RATE_LIMIT_DEFAULT`
- `REDIS_URL`
- `CELERY_BROKER_URL`

## Notes

- Celery and Redis integration are implemented as optional production hooks. In the current environment the app falls back to thread-based async processing.
- OpenTelemetry hooks are present, but full distributed export requires installing and configuring the OTel SDK/exporter stack.
- The facial landmark path uses a practical OpenCV fallback because MediaPipe and dlib are not installed in this environment.
- The audio-visual sync feature uses a proxy method, not SyncNet.

## License

No license file is currently bundled in the repository.
