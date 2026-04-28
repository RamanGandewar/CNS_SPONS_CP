from dataclasses import dataclass
from pathlib import Path

from utils.video_processing import get_video_metadata


@dataclass
class ValidationResult:
    valid: bool
    message: str = ""


class VideoValidator:
    """Validate uploaded/downloaded videos before model inference."""

    def __init__(self, max_size_mb=100, max_duration_seconds=180, min_duration_seconds=1):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_duration_seconds = max_duration_seconds
        self.min_duration_seconds = min_duration_seconds

    def validate(self, file_path):
        path = Path(file_path)
        if not path.exists():
            return ValidationResult(False, "Video file does not exist.")

        if path.stat().st_size <= 0:
            return ValidationResult(False, "Video file is empty.")

        if path.stat().st_size > self.max_size_bytes:
            return ValidationResult(False, "Video file is larger than 100MB.")

        if not self._has_mp4_signature(path):
            return ValidationResult(False, "Video container is not a valid MP4/MOV-style media file.")

        metadata = get_video_metadata(path)
        if metadata["frame_count"] <= 0:
            return ValidationResult(False, "Video has no readable frames.")

        duration = metadata["duration_seconds"]
        if duration < self.min_duration_seconds:
            return ValidationResult(False, "Video must be at least 1 second long.")

        if duration > self.max_duration_seconds:
            return ValidationResult(False, "Video must be 3 minutes or shorter.")

        return ValidationResult(True)

    @staticmethod
    def _has_mp4_signature(path):
        with Path(path).open("rb") as handle:
            header = handle.read(16)

        # ISO BMFF containers such as MP4/MOV normally expose "ftyp" at byte 4.
        return len(header) >= 12 and header[4:8] == b"ftyp"
