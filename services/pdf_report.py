from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def _artifact_path(image_url):
    return (Path.cwd() / image_url.lstrip("/")).resolve()


def _add_sampled_frame_pages(pdf, result):
    sampled_frames = result.get("artifacts", {}).get("sampled_frames", [])
    if not sampled_frames:
        sampled_frames = result.get("artifacts", {}).get("top_suspicious_frames", [])

    if not sampled_frames:
        return

    frames_per_page = 10
    for page_start in range(0, len(sampled_frames), frames_per_page):
        page_frames = sampled_frames[page_start:page_start + frames_per_page]
        page_number = page_start // frames_per_page + 1
        page_count = (len(sampled_frames) + frames_per_page - 1) // frames_per_page
        gallery = plt.figure(figsize=(11, 8.5))
        gallery.suptitle(
            f"Final Frame Review ({page_number}/{page_count}) - {result['verdict']['label']}",
            fontsize=16,
        )

        for index, frame in enumerate(page_frames, start=1):
            axis = gallery.add_subplot(2, 5, index)
            image_path = _artifact_path(frame["image_url"])
            if image_path.exists():
                axis.imshow(plt.imread(image_path))
            axis.set_title(
                f"Frame {frame['frame_number']}\n"
                f"{frame['score'] * 100:.2f}% fake",
                fontsize=9,
            )
            axis.set_xlabel(f"{float(frame['timestamp_seconds']):.2f}s", fontsize=8)
            axis.set_xticks([])
            axis.set_yticks([])

        gallery.text(
            0.05,
            0.03,
            f"Overall verdict: {result['verdict']['label']} | "
            f"Overall fake probability: {result['deepfake_percentage']} | "
            f"Frames reviewed: {len(sampled_frames)}",
            fontsize=10,
        )
        gallery.tight_layout(rect=[0.02, 0.07, 0.98, 0.92])
        pdf.savefig(gallery)
        plt.close(gallery)


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
                image = plt.imread(_artifact_path(frame["image_url"]))
                axis.imshow(image)
                axis.set_title(f"Frame {frame['frame_number']}\n{frame['score'] * 100:.2f}%")
                axis.axis("off")
            pdf.savefig(gallery)
            plt.close(gallery)

        _add_sampled_frame_pages(pdf, result)

    return output_path
