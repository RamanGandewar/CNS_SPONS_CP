from pathlib import Path

import cv2


def get_video_metadata(video_path):
    """Return basic video metadata used for limits and timestamps."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "frame_count": 0,
            "fps": 0.0,
            "duration_seconds": 0.0,
        }

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    cap.release()

    duration_seconds = frame_count / fps if fps > 0 else 0.0
    return {
        "frame_count": frame_count,
        "fps": fps,
        "duration_seconds": duration_seconds,
    }


def extract_frames(video_path, max_frames=20, frame_size=(224, 224), include_metadata=False):
    """
    Extract frames from a video file.
    """
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_interval = max(total_frames // max_frames, 1)
    frames = []
    count = 0

    while len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if count % frame_interval == 0:
            resized_frame = cv2.resize(frame, frame_size)
            if include_metadata:
                frames.append({
                    "frame": resized_frame,
                    "frame_number": count,
                    "timestamp_seconds": count / fps if fps > 0 else 0.0,
                })
            else:
                frames.append(resized_frame)
        count += 1

    cap.release()
    return frames


def save_frame_image(frame, output_path):
    """Persist a BGR OpenCV frame for frontend inspection."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), frame)

def preprocess_frame(frame):
    """
    Preprocess frame for the TFLite model.
    Normalize to [0, 1] range and resize if needed.
    """
    frame = frame / 255.0  # Normalize pixel values
    return frame

