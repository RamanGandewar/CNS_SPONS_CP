import json
import os
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import jwt
import numpy as np
import tensorflow as tf
from flask import Flask, Response, g, has_request_context, jsonify, render_template, request, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from services.auth import create_access_token, require_auth
from services.explainability import generate_gradcam_overlay, gradcam_status
from services.forensics import (
    audio_visual_sync,
    facial_landmark_displacement,
    frequency_domain_analysis,
    optical_flow_consistency,
)
from services.logging_utils import configure_logging, log_event
from services.pdf_report import build_forensic_report
from services.tracing import traced_span
from services.validator import VideoValidator
from utils.video_processing import extract_frames, get_video_metadata, preprocess_frame, save_frame_image

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    Limiter = None
    get_remote_address = None

try:
    from celery import Celery
except ImportError:
    Celery = None

if load_dotenv:
    load_dotenv()

configure_logging()
LOGGER = __import__("logging").getLogger("frametruth")

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ARTIFACT_FOLDER = BASE_DIR / "static" / "analysis"
REPORT_FOLDER = BASE_DIR / "static" / "reports"
DATA_FOLDER = BASE_DIR / "data"
DATABASE_PATH = DATA_FOLDER / "deepfake_detector.sqlite3"
MODEL_FOLDER = BASE_DIR / "model"
NOTEBOOK_EXPORTS = BASE_DIR / "notebooks_converted"
MODEL_METADATA_PATH = MODEL_FOLDER / "metadata.json"
CALIBRATION_PATH = MODEL_FOLDER / "calibration.json"
ALLOWED_EXTENSIONS = {"mp4", "mov"}
MAX_URL_DURATION_SECONDS = int(os.environ.get("MAX_VIDEO_DURATION_SECONDS", "180"))
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "20"))
SUSPICIOUS_THRESHOLD = 0.7
APP_VERSION = "2.0.0"
START_TIME = time.time()
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
MODEL_FILES = [
    MODEL_FOLDER / "deepfake_detector_model_final.tflite",
    MODEL_FOLDER / "deepfake_detector_model4.tflite",
]

for folder in (UPLOAD_FOLDER, ARTIFACT_FOLDER, REPORT_FOLDER, DATA_FOLDER, NOTEBOOK_EXPORTS):
    folder.mkdir(parents=True, exist_ok=True)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "replace-this-secret-before-production")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024

if CORS:
    origins = os.environ.get("CORS_ORIGINS", "http://127.0.0.1:5000,http://localhost:5000").split(",")
    CORS(app, origins=[origin.strip() for origin in origins if origin.strip()], supports_credentials=False)

if Limiter:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[os.environ.get("RATE_LIMIT_DEFAULT", "100 per day"), "10 per minute"],
        storage_uri=os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://"),
    )
else:
    limiter = None

validator = VideoValidator(
    max_size_mb=int(os.environ.get("MAX_UPLOAD_MB", "100")),
    max_duration_seconds=MAX_URL_DURATION_SECONDS,
    min_duration_seconds=1,
)


def load_model_registry():
    if MODEL_METADATA_PATH.exists():
        with MODEL_METADATA_PATH.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    else:
        metadata = {"models": []}

    if isinstance(metadata, dict) and "models" not in metadata:
        metadata = {"models": [metadata]}

    for item, model_path in zip(metadata.get("models", []), MODEL_FILES):
        item.setdefault("artifact", model_path.name)

    return metadata


def load_calibration_config():
    if CALIBRATION_PATH.exists():
        with CALIBRATION_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {"method": "identity", "a": 1.0, "b": 0.0}


MODEL_REGISTRY = load_model_registry()
CALIBRATION = load_calibration_config()


def build_interpreter(model_path):
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    return {
        "path": model_path,
        "interpreter": interpreter,
        "input_details": interpreter.get_input_details(),
        "output_details": interpreter.get_output_details(),
    }


MODEL_RUNNERS = [build_interpreter(model_path) for model_path in MODEL_FILES if model_path.exists()]

jobs = {}
jobs_lock = threading.Lock()

celery_app = None
if Celery is not None and os.environ.get("ENABLE_CELERY", "0") == "1":
    celery_app = Celery("frametruth", broker=CELERY_BROKER_URL, backend=CELERY_BROKER_URL)


def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'analyst',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                job_id TEXT,
                user_id INTEGER,
                source_type TEXT NOT NULL,
                status TEXT NOT NULL,
                verdict_label TEXT,
                confidence REAL,
                processing_time_seconds REAL,
                frames_analyzed INTEGER,
                report_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                user_id INTEGER,
                role TEXT,
                action TEXT NOT NULL,
                ip_address TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        migrate_schema(connection)


def ensure_column(connection, table_name, column_name, definition):
    columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def migrate_schema(connection):
    ensure_column(connection, "users", "role", "TEXT NOT NULL DEFAULT 'analyst'")
    ensure_column(connection, "analyses", "report_path", "TEXT")


def json_response(status, request_id, data=None, error=None, status_code=200):
    payload = {"request_id": request_id, "status": status}
    if error is not None:
        payload["error"] = error
    else:
        payload["data"] = data or {}
    return jsonify(payload), status_code


@app.before_request
def assign_request_id():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def add_headers(response):
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; "
        "img-src 'self' data:; "
        "connect-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'"
    )
    return response


def current_user():
    claims = getattr(g, "auth_user", None)
    if not claims:
        return None
    return {
        "id": int(claims["sub"]),
        "name": claims["name"],
        "email": claims["email"],
        "role": claims["role"],
    }


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def record_audit(action, user=None, details=None, request_id=None, ip_address=None):
    details = details or {}
    effective_request_id = request_id or getattr(g, "request_id", str(uuid.uuid4()))
    effective_ip = ip_address
    if effective_ip is None and has_request_context():
        effective_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO audit_log (request_id, user_id, role, action, ip_address, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                effective_request_id,
                user["id"] if user else None,
                user["role"] if user else None,
                action,
                effective_ip,
                json.dumps(details),
            ),
        )


def redis_health():
    parsed = urlparse(REDIS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return {"reachable": True, "host": host, "port": port}
    except OSError:
        return {"reachable": False, "host": host, "port": port}


def celery_health():
    if celery_app is None:
        return {"enabled": False, "worker_count": 0, "mode": "thread_fallback"}
    try:
        inspector = celery_app.control.inspect(timeout=1.0)
        active = inspector.ping() or {}
        return {"enabled": True, "worker_count": len(active), "mode": "celery"}
    except Exception:
        return {"enabled": True, "worker_count": 0, "mode": "celery_unreachable"}


def db_health():
    try:
        with get_db() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"reachable": True}
    except sqlite3.Error:
        return {"reachable": False}


def health_payload():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 3),
        "db": db_health(),
        "redis": redis_health(),
        "celery": celery_health(),
        "models_loaded": len(MODEL_RUNNERS),
    }


def verdict_for_score(score):
    if score < 0.3:
        return {"label": "Likely Real", "tone": "real", "explanation": "The sampled frames stayed mostly below the suspicious range."}
    if score < 0.6:
        return {"label": "Uncertain", "tone": "uncertain", "explanation": "The signal is mixed, so this result should be manually reviewed."}
    if score < 0.85:
        return {"label": "Likely Deepfake", "tone": "fake", "explanation": "Multiple sampled frames show elevated fake probability."}
    return {"label": "Almost Certainly Deepfake", "tone": "critical", "explanation": "The model reported consistently high fake probability."}


def calibrate_probability(score):
    method = CALIBRATION.get("method", "identity")
    if method == "platt":
        a = float(CALIBRATION.get("a", 1.0))
        b = float(CALIBRATION.get("b", 0.0))
        return float(1.0 / (1.0 + np.exp(-(a * score + b))))
    return float(score)


def predict_frame_ensemble(frame):
    processed_frame = np.expand_dims(preprocess_frame(frame), axis=0).astype(np.float32)
    raw_scores = []
    with traced_span("tflite_inference", runner_count=len(MODEL_RUNNERS)):
        for runner in MODEL_RUNNERS:
            interpreter = runner["interpreter"]
            interpreter.set_tensor(runner["input_details"][0]["index"], processed_frame)
            interpreter.invoke()
            prediction = interpreter.get_tensor(runner["output_details"][0]["index"])
            raw_scores.append(float(prediction[0][0]))

    mean_raw = float(np.mean(raw_scores)) if raw_scores else 0.0
    return {
        "raw_scores": raw_scores,
        "raw_average": mean_raw,
        "calibrated_score": calibrate_probability(mean_raw),
        "disagreement": float(np.std(raw_scores)) if raw_scores else 0.0,
    }


def consistency_for_scores(scores):
    std = float(np.std(scores)) if scores else 0.0
    mean = float(np.mean(scores)) if scores else 0.0
    if std >= 0.2:
        label = "High variation"
        explanation = "Frame scores swing noticeably, which can indicate splices or uncertain evidence."
    elif mean >= SUSPICIOUS_THRESHOLD:
        label = "Consistently suspicious"
        explanation = "Scores are stable and mostly high across sampled frames."
    elif mean <= 0.3:
        label = "Consistently low risk"
        explanation = "Scores are stable and mostly low across sampled frames."
    else:
        label = "Moderate variation"
        explanation = "Scores are not strongly clustered in either direction."
    return {
        "std": std,
        "variance": float(np.var(scores)) if scores else 0.0,
        "confidence": max(0.0, 1.0 - min(std / 0.35, 1.0)),
        "label": label,
        "explanation": explanation,
    }


def create_frame_artifacts(analysis_id, frame_items, scores):
    artifacts = []
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:3]
    for rank, (index, score) in enumerate(ranked, start=1):
        item = frame_items[index]
        filename = f"{analysis_id}_suspicious_{rank}.jpg"
        output_path = ARTIFACT_FOLDER / filename
        save_frame_image(item["frame"], output_path)
        artifacts.append({
            "rank": rank,
            "frame_number": item["frame_number"],
            "timestamp_seconds": item["timestamp_seconds"],
            "score": score,
            "image_url": f"/static/analysis/{filename}",
        })
    return artifacts


def maybe_generate_gradcam(result, frame_items):
    status = gradcam_status(MODEL_FOLDER)
    if not status["available"]:
        return status

    try:
        suspicious = max(enumerate(result["frame_scores"]), key=lambda item: item[1]["score"])[0]
        frame = frame_items[suspicious]["frame"]
        output_name = f"{result['analysis_id']}_gradcam.jpg"
        output_path = ARTIFACT_FOLDER / output_name
        overlay_path = generate_gradcam_overlay(status["model_path"], frame, output_path)
        status["overlay_url"] = f"/static/analysis/{Path(overlay_path).name}"
    except Exception as exc:
        status["available"] = False
        status["status"] = "gradcam_failed"
        status["message"] = str(exc)
    return status


def create_pdf_report(result):
    report_name = f"{result['analysis_id']}_report.pdf"
    report_path = REPORT_FOLDER / report_name
    build_forensic_report(result, report_path)
    return f"/api/v1/report/{result['analysis_id']}"


def analyze_video(video_path, source_type="upload", request_id=None):
    request_id = request_id or getattr(g, "request_id", str(uuid.uuid4()))
    with traced_span("analysis_pipeline", source_type=source_type, request_id=request_id):
        started = time.perf_counter()
        with traced_span("frame_extraction", max_frames=MAX_FRAMES):
            frame_items = extract_frames(video_path, max_frames=MAX_FRAMES, frame_size=(224, 224), include_metadata=True)
        if not frame_items:
            raise ValueError("No readable video frames were found.")

        frame_scores = []
        calibrated_scores = []
        disagreements = []
        for item in frame_items:
            prediction = predict_frame_ensemble(item["frame"])
            calibrated = prediction["calibrated_score"]
            calibrated_scores.append(calibrated)
            disagreements.append(prediction["disagreement"])
            frame_scores.append({
                "frame_number": item["frame_number"],
                "timestamp_seconds": round(float(item["timestamp_seconds"]), 3),
                "score": calibrated,
                "percentage": round(calibrated * 100, 2),
                "raw_model_scores": [round(score, 4) for score in prediction["raw_scores"]],
                "model_disagreement": round(prediction["disagreement"], 4),
                "suspicious": calibrated >= SUSPICIOUS_THRESHOLD,
            })

        analysis_id = uuid.uuid4().hex
        mean_score = float(np.mean(calibrated_scores))
        elapsed = time.perf_counter() - started
        result = {
            "analysis_id": analysis_id,
            "source_type": source_type,
            "deepfake_score": mean_score,
            "deepfake_percentage": f"{mean_score * 100:.2f}%",
            "verdict": verdict_for_score(mean_score),
            "frame_scores": frame_scores,
            "suspicious_markers": [item for item in frame_scores if item["suspicious"]],
            "consistency": consistency_for_scores(calibrated_scores),
            "metrics": {
                "processing_time_seconds": round(elapsed, 3),
                "frames_analyzed": len(frame_scores),
                "min_score": float(np.min(calibrated_scores)),
                "max_score": float(np.max(calibrated_scores)),
                "mean_score": mean_score,
                "std_score": float(np.std(calibrated_scores)),
                "p50_latency_ms": round((elapsed / max(len(frame_scores), 1)) * 1000, 2),
                "p95_model_disagreement": round(float(np.percentile(disagreements, 95)) if disagreements else 0.0, 4),
                "ensemble_size": len(MODEL_RUNNERS),
                "model_name": "FrameTruth Ensemble",
                "model_version": MODEL_REGISTRY.get("models", [{}])[0].get("version", "1.0.0"),
            },
            "artifacts": {
                "top_suspicious_frames": create_frame_artifacts(analysis_id, frame_items, calibrated_scores),
            },
        }

        with traced_span("forensics_signals"):
            result["forensics"] = {
                "frequency_analysis": frequency_domain_analysis(frame_items),
                "optical_flow": optical_flow_consistency(frame_items),
                "landmarks": facial_landmark_displacement(frame_items),
                "audio_visual_sync": audio_visual_sync(video_path, frame_items),
            }

        result["artifacts"]["gradcam"] = maybe_generate_gradcam(result, frame_items)
        result["report_url"] = create_pdf_report(result)
        return result


def persist_upload_or_url():
    source_type = "upload"
    if "video" in request.files and request.files["video"].filename:
        file = request.files["video"]
        if not allowed_file(file.filename):
            raise ValueError("Invalid file format. Upload an mp4 or mov video.")
        temp_path = UPLOAD_FOLDER / f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        file.save(temp_path)
    else:
        url = request.form.get("url")
        if not url and request.is_json:
            payload = request.get_json(silent=True) or {}
            url = payload.get("url")
        if not url:
            raise ValueError("Upload a video file or provide a public video URL.")
        if not shutil.which("yt-dlp"):
            raise ValueError("URL analysis needs yt-dlp installed.")
        temp_path = UPLOAD_FOLDER / f"url_{uuid.uuid4().hex}.mp4"
        command = [
            "yt-dlp",
            "--no-playlist",
            "--max-filesize",
            "100M",
            "--download-sections",
            f"*0-{MAX_URL_DURATION_SECONDS}",
            "-f",
            "mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
            "-o",
            str(temp_path),
            url.strip(),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=240)
        source_type = "url"

    validation = validator.validate(temp_path)
    if not validation.valid:
        temp_path.unlink(missing_ok=True)
        raise ValueError(validation.message)
    return temp_path, source_type


def record_analysis_success(request_id, job_id, user, result):
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO analyses (
                request_id, job_id, user_id, source_type, status, verdict_label,
                confidence, processing_time_seconds, frames_analyzed, report_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                job_id,
                user["id"],
                result["source_type"],
                "success",
                result["verdict"]["label"],
                result["deepfake_score"],
                result["metrics"]["processing_time_seconds"],
                result["metrics"]["frames_analyzed"],
                result["report_url"],
            ),
        )


def record_analysis_error(request_id, job_id, user, source_type, message):
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO analyses (request_id, job_id, user_id, source_type, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (request_id, job_id, user["id"], source_type, "error", message),
        )


def analytics_snapshot():
    with get_db() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS total_analyses,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS total_errors,
                AVG(CASE WHEN status = 'success' THEN confidence END) AS avg_confidence,
                AVG(CASE WHEN status = 'success' THEN processing_time_seconds END) AS avg_processing_time
            FROM analyses
            """
        ).fetchone()
        verdicts = connection.execute(
            """
            SELECT COALESCE(verdict_label, 'Error') AS label, COUNT(*) AS count
            FROM analyses GROUP BY COALESCE(verdict_label, 'Error') ORDER BY count DESC
            """
        ).fetchall()
        recent = connection.execute(
            """
            SELECT request_id, job_id, source_type, status, verdict_label, confidence,
                   processing_time_seconds, frames_analyzed, report_path, error_message, created_at
            FROM analyses ORDER BY datetime(created_at) DESC, id DESC LIMIT 10
            """
        ).fetchall()
        trend = connection.execute(
            """
            SELECT created_at, confidence, processing_time_seconds
            FROM analyses WHERE status = 'success'
            ORDER BY datetime(created_at) DESC, id DESC LIMIT 30
            """
        ).fetchall()

    confidences = [row["confidence"] for row in trend if row["confidence"] is not None]
    latencies = [row["processing_time_seconds"] for row in trend if row["processing_time_seconds"] is not None]
    return {
        "total_requests": summary["total_requests"] or 0,
        "total_analyses": summary["total_analyses"] or 0,
        "total_errors": summary["total_errors"] or 0,
        "average_confidence": summary["avg_confidence"] or 0.0,
        "average_processing_time_seconds": summary["avg_processing_time"] or 0.0,
        "p50_latency_seconds": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "p95_latency_seconds": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "p99_latency_seconds": float(np.percentile(latencies, 99)) if latencies else 0.0,
        "verdict_distribution": [dict(row) for row in verdicts],
        "recent_history": [dict(row) for row in recent],
        "confidence_over_time": [dict(row) for row in reversed(trend)],
        "health": health_payload(),
    }


def prometheus_metrics():
    snapshot = analytics_snapshot()
    lines = [
        "# HELP frametruth_analyses_total Total successful analyses.",
        "# TYPE frametruth_analyses_total counter",
        f"frametruth_analyses_total {snapshot['total_analyses']}",
        "# HELP frametruth_errors_total Total errors.",
        "# TYPE frametruth_errors_total counter",
        f"frametruth_errors_total {snapshot['total_errors']}",
        "# HELP frametruth_average_confidence Average confidence.",
        "# TYPE frametruth_average_confidence gauge",
        f"frametruth_average_confidence {snapshot['average_confidence']}",
        "# HELP frametruth_latency_p50_seconds p50 latency.",
        "# TYPE frametruth_latency_p50_seconds gauge",
        f"frametruth_latency_p50_seconds {snapshot['p50_latency_seconds']}",
        "# HELP frametruth_latency_p95_seconds p95 latency.",
        "# TYPE frametruth_latency_p95_seconds gauge",
        f"frametruth_latency_p95_seconds {snapshot['p95_latency_seconds']}",
        "# HELP frametruth_latency_p99_seconds p99 latency.",
        "# TYPE frametruth_latency_p99_seconds gauge",
        f"frametruth_latency_p99_seconds {snapshot['p99_latency_seconds']}",
    ]
    for item in snapshot["verdict_distribution"]:
        lines.append(f'frametruth_verdict_total{{verdict="{item["label"]}"}} {item["count"]}')
    return "\n".join(lines) + "\n"


def set_job(job_id, **updates):
    with jobs_lock:
        jobs.setdefault(job_id, {}).update(updates)
        return dict(jobs[job_id])


def get_job(job_id):
    with jobs_lock:
        item = jobs.get(job_id)
        return dict(item) if item else None


def process_job(job_id, request_id, user, temp_path, source_type):
    started = time.perf_counter()
    set_job(job_id, status="processing", progress=25)
    try:
        with app.app_context():
            result = analyze_video(temp_path, source_type=source_type, request_id=request_id)
        result["request_id"] = request_id
        result["job_id"] = job_id
        record_analysis_success(request_id, job_id, user, result)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            LOGGER,
            20,
            "analysis_complete",
            event="analysis_complete",
            request_id=request_id,
            job_id=job_id,
            user_id=user["id"],
            duration_ms=duration_ms,
            verdict=result["verdict"]["label"],
        )
        record_audit("analysis_complete", user, {"job_id": job_id, "verdict": result["verdict"]["label"]}, request_id=request_id)
        set_job(job_id, status="complete", progress=100, result=result)
    except Exception as exc:
        message = str(exc)
        record_analysis_error(request_id, job_id, user, source_type, message)
        log_event(
            LOGGER,
            40,
            "analysis_failed",
            event="analysis_failed",
            request_id=request_id,
            job_id=job_id,
            user_id=user["id"],
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        record_audit("analysis_failed", user, {"job_id": job_id, "error": message}, request_id=request_id)
        set_job(job_id, status="failed", progress=100, error=message)
    finally:
        temp_path.unlink(missing_ok=True)


def current_user_from_db(user_id):
    with get_db() as connection:
        row = connection.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify(health_payload())


@app.route("/metrics")
def metrics():
    return Response(prometheus_metrics(), mimetype="text/plain; version=0.0.4")


@app.route("/api/v1/model/info")
def model_info():
    payload = load_model_registry()
    payload["loaded_models"] = len(MODEL_RUNNERS)
    payload["calibration"] = CALIBRATION
    return json_response("success", g.request_id, payload)


@app.route("/api/v1/admin/analytics")
@require_auth({"operator", "admin"})
def admin_analytics():
    user = current_user()
    record_audit("admin_analytics_view", user)
    return json_response("success", g.request_id, analytics_snapshot())


@app.route("/api/v1/admin/users")
@require_auth({"admin"})
def admin_users():
    with get_db() as connection:
        rows = connection.execute("SELECT id, name, email, role, created_at FROM users ORDER BY id ASC").fetchall()
    record_audit("admin_users_list", current_user())
    return json_response("success", g.request_id, {"users": [dict(row) for row in rows]})


@app.route("/api/v1/admin/users/<int:user_id>/role", methods=["POST"])
@require_auth({"admin"})
def admin_update_role(user_id):
    payload = request.get_json(silent=True) or {}
    role = payload.get("role", "").strip()
    if role not in {"analyst", "operator", "admin"}:
        return json_response("error", g.request_id, error="Role must be analyst, operator, or admin.", status_code=400)
    with get_db() as connection:
        connection.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    record_audit("admin_role_update", current_user(), {"target_user_id": user_id, "role": role})
    return json_response("success", g.request_id, {"user_id": user_id, "role": role})


@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    try:
        with get_db() as connection:
            existing_users = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            role = "admin" if existing_users == 0 else "analyst"
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), role),
            )
        user = current_user_from_db(cursor.lastrowid)
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account already exists for that email."}), 409
    token = create_access_token(user)
    record_audit("signup", user)
    log_event(LOGGER, 20, "user_signup", event="user_signup", request_id=g.request_id, user_id=user["id"], role=user["role"])
    return jsonify({"user": user, "access_token": token}), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    with get_db() as connection:
        user = connection.execute(
            "SELECT id, name, email, role, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    public_user = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"],
    }
    token = create_access_token(public_user)
    record_audit("login", public_user)
    log_event(LOGGER, 20, "user_login", event="user_login", request_id=g.request_id, user_id=user["id"], role=user["role"])
    return jsonify({"user": public_user, "access_token": token})


@app.route("/api/auth/me", methods=["GET"])
@require_auth({"analyst", "operator", "admin"})
def auth_me():
    return jsonify({"user": current_user()})


@app.route("/api/auth/logout", methods=["POST"])
@require_auth({"analyst", "operator", "admin"})
def auth_logout():
    record_audit("logout", current_user())
    return jsonify({"ok": True})


@app.route("/api/v1/analyze", methods=["POST"])
@require_auth({"analyst", "operator", "admin"})
def api_v1_analyze():
    user = current_user()
    job_id = str(uuid.uuid4())
    source_type = "upload"
    try:
        with traced_span("validator", request_id=g.request_id, job_id=job_id):
            temp_path, source_type = persist_upload_or_url()
    except Exception as exc:
        record_analysis_error(g.request_id, job_id, user, source_type, str(exc))
        record_audit("analysis_submit_failed", user, {"error": str(exc)})
        return json_response("error", g.request_id, error=str(exc), status_code=400)

    record_audit("analysis_submitted", user, {"job_id": job_id})
    set_job(
        job_id,
        request_id=g.request_id,
        user_id=user["id"],
        status="processing",
        progress=10,
        result_url=f"/api/v1/result/{job_id}",
        report_url=None,
    )
    thread = threading.Thread(target=process_job, args=(job_id, g.request_id, user, temp_path, source_type), daemon=True)
    thread.start()
    return json_response("success", g.request_id, {
        "job_id": job_id,
        "status": "processing",
        "progress": 10,
        "poll_url": f"/api/v1/status/{job_id}",
        "result_url": f"/api/v1/result/{job_id}",
    }, status_code=202)


@app.route("/api/v1/status/<job_id>")
@require_auth({"analyst", "operator", "admin"})
def api_v1_status(job_id):
    user = current_user()
    job = get_job(job_id)
    if not job:
        return json_response("error", g.request_id, error="Job not found.", status_code=404)
    if user["role"] == "analyst" and job.get("user_id") != user["id"]:
        return json_response("error", g.request_id, error="Job not found.", status_code=404)
    return json_response("success", job["request_id"], {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "result_url": job.get("result_url"),
        "error": job.get("error"),
    })


@app.route("/api/v1/result/<job_id>")
@require_auth({"analyst", "operator", "admin"})
def api_v1_result(job_id):
    user = current_user()
    job = get_job(job_id)
    if not job:
        return json_response("error", g.request_id, error="Job not found.", status_code=404)
    if user["role"] == "analyst" and job.get("user_id") != user["id"]:
        return json_response("error", g.request_id, error="Job not found.", status_code=404)
    if job["status"] == "failed":
        return json_response("error", job["request_id"], error=job.get("error", "Analysis failed."), status_code=500)
    if job["status"] != "complete":
        return json_response("success", job["request_id"], {"job_id": job_id, "status": job["status"], "progress": job["progress"]}, status_code=202)
    return json_response("success", job["request_id"], job["result"])


@app.route("/api/v1/report/<analysis_id>")
@require_auth({"analyst", "operator", "admin"})
def api_v1_report(analysis_id):
    report_path = REPORT_FOLDER / f"{analysis_id}_report.pdf"
    if not report_path.exists():
        return json_response("error", g.request_id, error="Report not found.", status_code=404)
    return send_file(report_path, mimetype="application/pdf", as_attachment=True, download_name=report_path.name)


@app.route("/api/analyze", methods=["POST"])
@require_auth({"analyst", "operator", "admin"})
def api_analyze_sync():
    user = current_user()
    source_type = "upload"
    temp_path = None
    started = time.perf_counter()
    try:
        temp_path, source_type = persist_upload_or_url()
        result = analyze_video(temp_path, source_type=source_type, request_id=g.request_id)
        result["request_id"] = g.request_id
        record_analysis_success(g.request_id, None, user, result)
        record_audit("analysis_sync_complete", user, {"verdict": result["verdict"]["label"]})
        log_event(
            LOGGER,
            20,
            "analysis_sync_complete",
            event="analysis_sync_complete",
            request_id=g.request_id,
            user_id=user["id"],
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            verdict=result["verdict"]["label"],
        )
        return json_response("success", g.request_id, result)
    except Exception as exc:
        record_analysis_error(g.request_id, None, user, source_type, str(exc))
        record_audit("analysis_sync_failed", user, {"error": str(exc)})
        return json_response("error", g.request_id, error=str(exc), status_code=400)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


@app.route("/upload", methods=["POST"])
@require_auth({"analyst", "operator", "admin"})
def upload_alias():
    return api_analyze_sync()


init_db()


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
