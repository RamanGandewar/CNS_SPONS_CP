import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

try:
    import librosa
except ImportError:
    librosa = None


FACE_CASCADE = cv2.CascadeClassifier(
    str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
)


def frequency_domain_analysis(frame_items):
    frame_scores = []
    for item in frame_items:
        gray = cv2.cvtColor(item["frame"], cv2.COLOR_BGR2GRAY)
        spectrum = np.fft.fftshift(np.fft.fft2(gray))
        magnitude = np.log1p(np.abs(spectrum))
        high_frequency_ratio = float(np.mean(magnitude[gray.shape[0] // 4 :, gray.shape[1] // 4 :]) / (np.mean(magnitude) + 1e-6))
        frame_scores.append(min(high_frequency_ratio / 4.0, 1.0))

    return {
        "score": float(np.mean(frame_scores)) if frame_scores else 0.0,
        "frame_scores": [round(score, 4) for score in frame_scores],
        "method": "fft_high_frequency_ratio",
    }


def optical_flow_consistency(frame_items):
    magnitudes = []
    for left, right in zip(frame_items, frame_items[1:]):
        prev_gray = cv2.cvtColor(left["frame"], cv2.COLOR_BGR2GRAY)
        next_gray = cv2.cvtColor(right["frame"], cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(prev_gray, next_gray, None, 0.5, 3, 21, 3, 5, 1.2, 0)
        magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        magnitudes.append(float(np.std(magnitude) / (np.mean(magnitude) + 1e-6)))

    score = min(float(np.mean(magnitudes)) / 5.0, 1.0) if magnitudes else 0.0
    return {
        "score": score,
        "pair_scores": [round(item, 4) for item in magnitudes],
        "method": "farneback_motion_variance",
    }


def facial_landmark_displacement(frame_items):
    pair_displacements = []
    face_boxes = []
    for left, right in zip(frame_items, frame_items[1:]):
        prev_gray = cv2.cvtColor(left["frame"], cv2.COLOR_BGR2GRAY)
        next_gray = cv2.cvtColor(right["frame"], cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(prev_gray, scaleFactor=1.1, minNeighbors=4, minSize=(48, 48))
        if len(faces) == 0:
            continue

        x, y, w, h = faces[0]
        face_boxes.append({"frame_number": left["frame_number"], "bbox": [int(x), int(y), int(w), int(h)]})
        roi = prev_gray[y:y + h, x:x + w]
        points = cv2.goodFeaturesToTrack(roi, maxCorners=32, qualityLevel=0.01, minDistance=4)
        if points is None:
            continue

        points[:, 0, 0] += x
        points[:, 0, 1] += y
        next_points, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, next_gray, points, None)
        if next_points is None or status is None:
            continue

        valid_prev = points[status.flatten() == 1]
        valid_next = next_points[status.flatten() == 1]
        if len(valid_prev) == 0:
            continue

        displacement = np.linalg.norm(valid_next - valid_prev, axis=1)
        pair_displacements.append(float(np.mean(displacement)))

    score = min(float(np.std(pair_displacements)) / 6.0, 1.0) if pair_displacements else 0.0
    return {
        "score": score,
        "pair_displacements": [round(item, 4) for item in pair_displacements],
        "method": "haar_face_plus_shitomasi_fallback",
        "face_boxes": face_boxes,
        "semantic_mesh_available": False,
    }

def audio_visual_sync(video_path, frame_items):
    if librosa is None:
        return {"available": False, "reason": "librosa_not_installed"}

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return {"available": False, "reason": "ffmpeg_not_available"}

    with tempfile.TemporaryDirectory(prefix="frametruth-audio-") as temp_dir:
        audio_path = Path(temp_dir) / "audio.wav"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=120)
        except Exception:
            return {"available": False, "reason": "audio_extraction_failed"}

        try:
            audio_signal, sample_rate = librosa.load(audio_path, sr=16000)
        except Exception:
            return {"available": False, "reason": "audio_decode_failed"}

    if audio_signal.size == 0:
        return {"available": False, "reason": "audio_missing"}

    rms = librosa.feature.rms(y=audio_signal, frame_length=512, hop_length=256)[0]
    lower_face_motion = []
    for left, right in zip(frame_items, frame_items[1:]):
        prev_gray = cv2.cvtColor(left["frame"], cv2.COLOR_BGR2GRAY)
        next_gray = cv2.cvtColor(right["frame"], cv2.COLOR_BGR2GRAY)
        h = prev_gray.shape[0]
        mouth_prev = prev_gray[h // 2 :, :]
        mouth_next = next_gray[h // 2 :, :]
        lower_face_motion.append(float(np.mean(np.abs(mouth_next.astype(np.float32) - mouth_prev.astype(np.float32)))))

    if not lower_face_motion:
        return {"available": False, "reason": "insufficient_frames"}

    motion = np.array(lower_face_motion, dtype=np.float32)
    rms = np.interp(np.linspace(0, len(rms) - 1, num=len(motion)), np.arange(len(rms)), rms)
    correlation = float(np.corrcoef(motion, rms)[0, 1]) if len(motion) > 1 else 0.0
    correlation = 0.0 if np.isnan(correlation) else correlation
    return {
        "available": True,
        "score": round((correlation + 1.0) / 2.0, 4),
        "raw_correlation": round(correlation, 4),
        "method": "audio_rms_vs_lower_face_motion_proxy",
        "pretrained_syncnet_available": False,
    }


def serialize_for_report(result):
    return {
        "request_id": result.get("request_id"),
        "verdict": result.get("verdict", {}),
        "deepfake_percentage": result.get("deepfake_percentage"),
        "metrics": result.get("metrics", {}),
        "consistency": result.get("consistency", {}),
        "frequency_analysis": result.get("forensics", {}).get("frequency_analysis", {}),
        "optical_flow": result.get("forensics", {}).get("optical_flow", {}),
        "landmarks": result.get("forensics", {}).get("landmarks", {}),
    }
