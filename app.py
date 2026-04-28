import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from functools import wraps
from pathlib import Path

import numpy as np
import tensorflow as tf
from flask import Flask, Response, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from services.validator import VideoValidator
from utils.video_processing import extract_frames, preprocess_frame, save_frame_image

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


if load_dotenv:
    load_dotenv()

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("frametruth")

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ARTIFACT_FOLDER = BASE_DIR / "static" / "analysis"
DATA_FOLDER = BASE_DIR / "data"
DATABASE_PATH = DATA_FOLDER / "deepfake_detector.sqlite3"
MODEL_FOLDER = BASE_DIR / "model"
MODEL_METADATA_PATH = MODEL_FOLDER / "metadata.json"
ALLOWED_EXTENSIONS = {"mp4", "mov"}
MAX_URL_DURATION_SECONDS = int(os.environ.get("MAX_VIDEO_DURATION_SECONDS", "180"))
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "20"))
SUSPICIOUS_THRESHOLD = 0.7
MODEL_NAME = "Deepfake Detector TFLite"
MODEL_VERSION = "deepfake_detector_model_final.tflite"
APP_VERSION = "1.0.0"
START_TIME = time.time()

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ARTIFACT_FOLDER.mkdir(parents=True, exist_ok=True)
DATA_FOLDER.mkdir(parents=True, exist_ok=True)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "replace-this-secret-before-production")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024

if CORS:
    origins = os.environ.get("CORS_ORIGINS", "http://127.0.0.1:5000,http://localhost:5000").split(",")
    CORS(app, origins=[origin.strip() for origin in origins if origin.strip()], supports_credentials=True)

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

TFLITE_MODEL_PATH = MODEL_FOLDER / MODEL_VERSION
interpreter = tf.lite.Interpreter(model_path=str(TFLITE_MODEL_PATH))
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

jobs = {}
jobs_lock = threading.Lock()


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
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def load_model_metadata():
    if MODEL_METADATA_PATH.exists():
        with MODEL_METADATA_PATH.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    else:
        metadata = {}

    metadata.setdefault("name", MODEL_NAME)
    metadata.setdefault("version", APP_VERSION)
    metadata.setdefault("artifact", MODEL_VERSION)
    metadata["loaded"] = interpreter is not None
    metadata["path"] = str(TFLITE_MODEL_PATH.relative_to(BASE_DIR))
    return metadata


def api_success(data=None, status_code=200, request_id=None):
    return jsonify({
        "request_id": request_id or getattr(g, "request_id", str(uuid.uuid4())),
        "status": "success",
        "data": data if data is not None else {},
    }), status_code


def api_error(message, status_code=400, request_id=None):
    return jsonify({
        "request_id": request_id or getattr(g, "request_id", str(uuid.uuid4())),
        "status": "error",
        "error": message,
    }), status_code


@app.before_request
def assign_request_id():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def add_security_headers(response):
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
    user_id = session.get("user_id")
    if not user_id:
        return None

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    return dict(user) if user else None


def require_auth(route_handler):
    @wraps(route_handler)
    def wrapper(*args, **kwargs):
        if not current_user():
            return api_error("Sign in before running an analysis.", 401)
        return route_handler(*args, **kwargs)

    return wrapper


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def verdict_for_score(score):
    if score < 0.3:
        return {
            "label": "Likely Real",
            "tone": "real",
            "explanation": "The sampled frames stayed mostly below the suspicious range.",
        }
    if score < 0.6:
        return {
            "label": "Uncertain",
            "tone": "uncertain",
            "explanation": "The signal is mixed, so this result should be manually reviewed.",
        }
    if score < 0.85:
        return {
            "label": "Likely Deepfake",
            "tone": "fake",
            "explanation": "Multiple sampled frames show elevated fake probability.",
        }
    return {
        "label": "Almost Certainly Deepfake",
        "tone": "critical",
        "explanation": "The model reported consistently high fake probability.",
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


def predict_frame(frame):
    processed_frame = preprocess_frame(frame)
    processed_frame = np.expand_dims(processed_frame, axis=0).astype(np.float32)
    interpreter.set_tensor(input_details[0]["index"], processed_frame)
    interpreter.invoke()
    prediction = interpreter.get_tensor(output_details[0]["index"])
    return float(prediction[0][0])


def create_frame_artifacts(analysis_id, frame_items, scores):
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:3]
    artifacts = []
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


def gradcam_status():
    h5_models = sorted(MODEL_FOLDER.glob("*.h5")) + sorted(MODEL_FOLDER.glob("*.keras"))
    if h5_models:
        return {
            "available": False,
            "status": "keras_model_present",
            "message": "A Keras model exists, but Grad-CAM layer mapping still needs model-specific configuration.",
        }
    return {
        "available": False,
        "status": "needs_keras_model",
        "message": "Grad-CAM requires a .h5/.keras model with accessible intermediate layers; this project currently ships TFLite models only.",
    }


def analyze_video(video_path, source_type="upload"):
    start_time = time.perf_counter()
    frame_items = extract_frames(
        video_path,
        max_frames=MAX_FRAMES,
        frame_size=(224, 224),
        include_metadata=True,
    )
    if not frame_items:
        raise ValueError("No readable video frames were found.")

    scores = [predict_frame(item["frame"]) for item in frame_items]
    frame_scores = [
        {
            "frame_number": item["frame_number"],
            "timestamp_seconds": round(float(item["timestamp_seconds"]), 3),
            "score": score,
            "percentage": round(score * 100, 2),
            "suspicious": score >= SUSPICIOUS_THRESHOLD,
        }
        for item, score in zip(frame_items, scores)
    ]

    mean_score = float(np.mean(scores))
    analysis_id = uuid.uuid4().hex
    elapsed = time.perf_counter() - start_time

    return {
        "analysis_id": analysis_id,
        "source_type": source_type,
        "deepfake_score": mean_score,
        "deepfake_percentage": f"{mean_score * 100:.2f}%",
        "verdict": verdict_for_score(mean_score),
        "frame_scores": frame_scores,
        "suspicious_markers": [item for item in frame_scores if item["suspicious"]],
        "consistency": consistency_for_scores(scores),
        "metrics": {
            "processing_time_seconds": round(elapsed, 3),
            "frames_analyzed": len(scores),
            "min_score": float(np.min(scores)),
            "max_score": float(np.max(scores)),
            "mean_score": mean_score,
            "std_score": float(np.std(scores)),
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
        },
        "artifacts": {
            "top_suspicious_frames": create_frame_artifacts(analysis_id, frame_items, scores),
            "gradcam": gradcam_status(),
        },
    }


def download_video(url):
    if not url.startswith(("http://", "https://")):
        raise ValueError("Enter a valid http(s) video URL.")
    if not shutil.which("yt-dlp"):
        raise ValueError("URL analysis needs yt-dlp installed. Run pip install -r requirements.txt.")

    output_template = str(UPLOAD_FOLDER / f"url_{uuid.uuid4().hex}.%(ext)s")
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
        output_template,
        url,
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=240)
    candidates = sorted(UPLOAD_FOLDER.glob("url_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise ValueError("The URL video could not be downloaded.")
    return candidates[0]


def persist_upload_or_url():
    source_type = "upload"
    if "video" in request.files and request.files["video"].filename:
        file = request.files["video"]
        if not allowed_file(file.filename):
            raise ValueError("Invalid file format. Upload an mp4 or mov video.")

        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        temp_path = UPLOAD_FOLDER / filename
        file.save(temp_path)
    else:
        url = request.form.get("url")
        if not url and request.is_json:
            payload = request.get_json(silent=True) or {}
            url = payload.get("url")
        if not url:
            raise ValueError("Upload a video file or provide a video URL.")
        source_type = "url"
        temp_path = download_video(url.strip())

    validation = validator.validate(temp_path)
    if not validation.valid:
        temp_path.unlink(missing_ok=True)
        raise ValueError(validation.message)

    return temp_path, source_type


def record_analysis_success(request_id, job_id, user_id, result):
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO analyses (
                request_id, job_id, user_id, source_type, status, verdict_label,
                confidence, processing_time_seconds, frames_analyzed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                job_id,
                user_id,
                result["source_type"],
                "success",
                result["verdict"]["label"],
                result["deepfake_score"],
                result["metrics"]["processing_time_seconds"],
                result["metrics"]["frames_analyzed"],
            ),
        )


def record_analysis_error(request_id, job_id, user_id, source_type, message):
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO analyses (
                request_id, job_id, user_id, source_type, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (request_id, job_id, user_id, source_type, "error", message),
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
            FROM analyses
            GROUP BY COALESCE(verdict_label, 'Error')
            ORDER BY count DESC
            """
        ).fetchall()
        recent = connection.execute(
            """
            SELECT request_id, job_id, source_type, status, verdict_label, confidence,
                   processing_time_seconds, frames_analyzed, error_message, created_at
            FROM analyses
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 10
            """
        ).fetchall()
        trend = connection.execute(
            """
            SELECT created_at, confidence
            FROM analyses
            WHERE status = 'success'
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 20
            """
        ).fetchall()
        errors_last_hour = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM analyses
            WHERE status = 'error' AND datetime(created_at) >= datetime('now', '-1 hour')
            """
        ).fetchone()

    return {
        "total_requests": summary["total_requests"] or 0,
        "total_analyses": summary["total_analyses"] or 0,
        "total_errors": summary["total_errors"] or 0,
        "average_confidence": summary["avg_confidence"] or 0.0,
        "average_processing_time_seconds": summary["avg_processing_time"] or 0.0,
        "verdict_distribution": [dict(row) for row in verdicts],
        "recent_history": [dict(row) for row in recent],
        "confidence_over_time": [dict(row) for row in reversed(trend)],
        "errors_last_hour": errors_last_hour["count"] or 0,
        "health": health_payload(),
    }


def prometheus_metrics():
    snapshot = analytics_snapshot()
    verdict_lines = [
        f'frametruth_verdict_total{{verdict="{item["label"]}"}} {item["count"]}'
        for item in snapshot["verdict_distribution"]
    ]
    lines = [
        "# HELP frametruth_analyses_total Total successful video analyses.",
        "# TYPE frametruth_analyses_total counter",
        f"frametruth_analyses_total {snapshot['total_analyses']}",
        "# HELP frametruth_errors_total Total analysis errors.",
        "# TYPE frametruth_errors_total counter",
        f"frametruth_errors_total {snapshot['total_errors']}",
        "# HELP frametruth_average_confidence Average deepfake confidence score.",
        "# TYPE frametruth_average_confidence gauge",
        f"frametruth_average_confidence {snapshot['average_confidence']}",
        "# HELP frametruth_average_processing_seconds Average processing time.",
        "# TYPE frametruth_average_processing_seconds gauge",
        f"frametruth_average_processing_seconds {snapshot['average_processing_time_seconds']}",
        "# HELP frametruth_uptime_seconds Service uptime.",
        "# TYPE frametruth_uptime_seconds gauge",
        f"frametruth_uptime_seconds {snapshot['health']['uptime_seconds']}",
        *verdict_lines,
    ]
    return "\n".join(lines) + "\n"


def health_payload():
    return {
        "status": "ok",
        "model_loaded": interpreter is not None,
        "uptime_seconds": round(time.time() - START_TIME, 3),
        "version": APP_VERSION,
        "model_version": MODEL_VERSION,
    }


def set_job(job_id, **updates):
    with jobs_lock:
        jobs.setdefault(job_id, {}).update(updates)
        return dict(jobs[job_id])


def get_job(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        return dict(job) if job else None


def process_job(job_id, request_id, user_id, temp_path, source_type):
    set_job(job_id, status="processing", progress=25)
    try:
        result = analyze_video(temp_path, source_type=source_type)
        result["request_id"] = request_id
        result["job_id"] = job_id
        record_analysis_success(request_id, job_id, user_id, result)
        set_job(job_id, status="complete", progress=100, result=result)
        logger.info("analysis_complete request_id=%s job_id=%s", request_id, job_id)
    except Exception as exc:
        message = str(exc)
        record_analysis_error(request_id, job_id, user_id, source_type, message)
        set_job(job_id, status="failed", progress=100, error=message)
        logger.exception("analysis_failed request_id=%s job_id=%s", request_id, job_id)
    finally:
        temp_path.unlink(missing_ok=True)


def run_sync_analysis():
    user = current_user()
    temp_path = None
    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    source_type = "upload"
    try:
        temp_path, source_type = persist_upload_or_url()
        result = analyze_video(temp_path, source_type=source_type)
        result["request_id"] = request_id
        record_analysis_success(request_id, None, user["id"], result)
        return api_success(result)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "The video URL could not be downloaded."
        record_analysis_error(request_id, None, user["id"], source_type, detail)
        return api_error(detail, 400)
    except (ValueError, OSError, TimeoutError) as exc:
        record_analysis_error(request_id, None, user["id"], source_type, str(exc))
        return api_error(str(exc), 400)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


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
    return api_success(load_model_metadata())


@app.route("/api/v1/admin/analytics")
@require_auth
def admin_analytics():
    return api_success(analytics_snapshot())


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    return jsonify({"user": current_user()})


@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400
    if "@" not in email:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            session["user_id"] = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account already exists for that email."}), 409

    return jsonify({"user": current_user()}), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, name, email, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"] = user["id"]
    return jsonify({
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "created_at": user["created_at"],
        }
    })


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/v1/analyze", methods=["POST"])
@require_auth
def api_v1_analyze():
    user = current_user()
    request_id = getattr(g, "request_id", str(uuid.uuid4()))
    job_id = str(uuid.uuid4())
    source_type = "upload"
    try:
        temp_path, source_type = persist_upload_or_url()
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "The video URL could not be downloaded."
        record_analysis_error(request_id, job_id, user["id"], source_type, detail)
        return api_error(detail, 400, request_id=request_id)
    except (ValueError, OSError, TimeoutError) as exc:
        record_analysis_error(request_id, job_id, user["id"], source_type, str(exc))
        return api_error(str(exc), 400, request_id=request_id)

    set_job(
        job_id,
        request_id=request_id,
        user_id=user["id"],
        status="processing",
        progress=10,
        created_at=time.time(),
        poll_url=f"/api/v1/status/{job_id}",
        result_url=f"/api/v1/result/{job_id}",
    )
    thread = threading.Thread(
        target=process_job,
        args=(job_id, request_id, user["id"], temp_path, source_type),
        daemon=True,
    )
    thread.start()
    return api_success({
        "job_id": job_id,
        "status": "processing",
        "progress": 10,
        "poll_url": f"/api/v1/status/{job_id}",
        "result_url": f"/api/v1/result/{job_id}",
    }, status_code=202, request_id=request_id)


@app.route("/api/v1/status/<job_id>")
@require_auth
def api_v1_status(job_id):
    user = current_user()
    job = get_job(job_id)
    if not job or job.get("user_id") != user["id"]:
        return api_error("Job not found.", 404)
    return api_success({
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "poll_url": job.get("poll_url"),
        "result_url": job.get("result_url"),
        "error": job.get("error"),
    }, request_id=job["request_id"])


@app.route("/api/v1/result/<job_id>")
@require_auth
def api_v1_result(job_id):
    user = current_user()
    job = get_job(job_id)
    if not job or job.get("user_id") != user["id"]:
        return api_error("Job not found.", 404)
    if job["status"] == "failed":
        return api_error(job.get("error", "Analysis failed."), 500, request_id=job["request_id"])
    if job["status"] != "complete":
        return api_success({
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
        }, status_code=202, request_id=job["request_id"])
    return api_success(job["result"], request_id=job["request_id"])


@app.route("/upload", methods=["POST"])
@require_auth
def upload():
    return run_sync_analysis()


@app.route("/api/analyze", methods=["POST"])
@require_auth
def api_analyze():
    return run_sync_analysis()


init_db()


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
