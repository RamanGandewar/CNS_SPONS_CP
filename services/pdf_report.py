from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def build_forensic_report(result, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(output_path) as pdf:
        figure = plt.figure(figsize=(11, 8.5))
        figure.suptitle("FrameTruth AI Forensic Report", fontsize=18)
        summary = [
            f"Request ID: {result.get('request_id', 'n/a')}",
            f"Verdict: {result['verdict']['label']}",
            f"Deepfake Probability: {result['deepfake_percentage']}",
            f"Processing Time: {result['metrics']['processing_time_seconds']}s",
            f"Frames Analysed: {result['metrics']['frames_analyzed']}",
            f"Model: {result['metrics']['model_name']} ({result['metrics']['model_version']})",
        ]
        figure.text(0.08, 0.72, "\n".join(summary), fontsize=12)
        figure.text(0.08, 0.42, f"Consistency: {result['consistency']['label']}", fontsize=12)
        figure.text(0.08, 0.38, result['consistency']['explanation'], fontsize=11, wrap=True)
        pdf.savefig(figure)
        plt.close(figure)

        timeline = plt.figure(figsize=(11, 8.5))
        axis = timeline.add_subplot(111)
        axis.plot(
            [item["timestamp_seconds"] for item in result["frame_scores"]],
            [item["percentage"] for item in result["frame_scores"]],
            color="#d1495b",
            linewidth=2,
        )
        axis.axhline(y=70, color="#2e86ab", linestyle="--", linewidth=1.2)
        axis.set_title("Fake Probability Timeline")
        axis.set_xlabel("Timestamp (seconds)")
        axis.set_ylabel("Probability (%)")
        axis.set_ylim(0, 100)
        pdf.savefig(timeline)
        plt.close(timeline)

        suspicious_frames = result.get("artifacts", {}).get("top_suspicious_frames", [])
        if suspicious_frames:
            gallery = plt.figure(figsize=(11, 8.5))
            for index, frame in enumerate(suspicious_frames[:3], start=1):
                axis = gallery.add_subplot(1, 3, index)
                image = plt.imread((Path.cwd() / frame["image_url"].lstrip("/")).resolve())
                axis.imshow(image)
                axis.set_title(f"Frame {frame['frame_number']}\n{frame['score'] * 100:.2f}%")
                axis.axis("off")
            pdf.savefig(gallery)
            plt.close(gallery)

    return output_path
