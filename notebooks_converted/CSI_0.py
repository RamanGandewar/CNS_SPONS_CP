# Auto-exported from CSI_0.ipynb

import os
import cv2
import random
import numpy as np
import pickle
from tqdm import tqdm
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# %%

# Paths to dataset folders
DATASET_DIR = "dataset"
REAL_DIR = os.path.join(DATASET_DIR, "Celeb-real")
SYNTHESIS_DIR = os.path.join(DATASET_DIR, "Celeb-synthesis")

# Parameters
FRAME_RATE = 1
FRAME_SIZE = (224, 224)
AUGMENTATION = True

# %%

def extract_limited_frames(video_path, output_dir, max_frames=20, frame_size=(224, 224)):
    """
    Extract frames from the first 10 seconds of a video, limiting the total number of frames.
    - video_path: Path to the video file.
    - output_dir: Directory where frames will be saved.
    - max_frames: Maximum number of frames to extract (default: 30).
    - frame_size: Tuple specifying the size to resize frames (default: 224x224).
    """
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)

    fps = int(cap.get(cv2.CAP_PROP_FPS))  # Frames per second of the video
    total_frames = int(min(cap.get(cv2.CAP_PROP_FRAME_COUNT), fps * 10))  # Max frames in 10 seconds
    frame_interval = max(total_frames // max_frames, 1)  # Interval to evenly distribute frames

    frame_count = 0
    saved_frames = 0

    while saved_frames < max_frames:
        ret, frame = cap.read()
        if not ret or frame_count >= total_frames:
            break
        if frame_count % frame_interval == 0:
            frame = cv2.resize(frame, frame_size)  # Resize the frame
            frame_filename = os.path.join(output_dir, f"frame_{saved_frames:04d}.jpg")
            cv2.imwrite(frame_filename, frame)  # Save the frame as an image
            saved_frames += 1
        frame_count += 1

    cap.release()
    print(f"Extracted {saved_frames} frames from the first 10 seconds of {video_path}")

# %%

def process_videos_limited_frames(input_dir, output_dir, max_frames=20, frame_size=(224, 224)):
    """
    Process all videos in the input directory to extract limited frames.
    """
    os.makedirs(output_dir, exist_ok=True)

    for video in tqdm(os.listdir(input_dir), desc=f"Processing videos in {input_dir}"):
        if video.endswith(".mp4"):
            video_path = os.path.join(input_dir, video)
            video_output_dir = os.path.join(output_dir, os.path.splitext(video)[0])
            extract_limited_frames(video_path, video_output_dir, max_frames, frame_size)

# Paths
REAL_DIR = "dataset/Celeb-real"
SYNTHESIS_DIR = "dataset/Celeb-synthesis"
OUTPUT_DIR = "processed_frames"

# Extract frames for real and synthesized videos
process_videos_limited_frames(REAL_DIR, os.path.join(OUTPUT_DIR, "Celeb-real"))
process_videos_limited_frames(SYNTHESIS_DIR, os.path.join(OUTPUT_DIR, "Celeb-synthesis"))

# %%

REAL_DIR = "dataset/Celeb-real"
SYNTHESIS_DIR = "dataset/Celeb-synthesis"
OUTPUT_DIR = "processed_frames"

# %%

from google.colab import drive
drive.mount('/content/drive')

# %%

!cp -r /content/processed_frames /content/drive/MyDrive/

# %%

def process_and_save_batches(base_dir, output_dir, frame_size=(224, 224), batch_size=100):
    """
    Process frames in batches and save them to disk.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for folder_name, label in [("Celeb-real", 0), ("Celeb-synthesis", 1)]:
        folder_path = os.path.join(base_dir, folder_name)
        batch_idx = 0

        for video_folder in tqdm(os.listdir(folder_path), desc=f"Processing {folder_name} in batches"):
            video_path = os.path.join(folder_path, video_folder)
            if os.path.isdir(video_path):
                frames = []
                labels = []
                for frame in os.listdir(video_path):
                    if frame.endswith(".jpg"):
                        frame_path = os.path.join(video_path, frame)
                        image = cv2.imread(frame_path)
                        if image is not None:
                            image = cv2.resize(image, frame_size)
                            image = image / 255.0
                            frames.append(image)
                            labels.append(label)

                    if len(frames) == batch_size:  # Save batch
                        save_path = os.path.join(output_dir, f"{folder_name}_batch_{batch_idx}.pkl")
                        with open(save_path, "wb") as f:
                            pickle.dump((np.array(frames), np.array(labels)), f)
                        frames, labels = [], []
                        batch_idx += 1

                # Save any remaining frames
                if frames:
                    save_path = os.path.join(output_dir, f"{folder_name}_batch_{batch_idx}.pkl")
                    with open(save_path, "wb") as f:
                        pickle.dump((np.array(frames), np.array(labels)), f)

# Specify directories
base_directory = "/content/processed_frames"  # Replace with your dataset folder
output_directory = "processed_batches"  # Replace or set as needed

process_and_save_batches(base_directory, output_directory)

# %%

#dont run this code
from google.colab import drive
drive.mount('/content/drive')

import os
os.chdir('/content/drive/MyDrive/processed_frames')

# List files in the folder
print(os.listdir())

# %%

!fusermount -u /content/drive
!rm -rf /content/drive

# %%

# Define paths
base_dir = '/content/drive/MyDrive/processed_frames'
real_dir = os.path.join(base_dir, 'Celeb-real')
fake_dir = os.path.join(base_dir, 'Celeb-synthesis')

# Prepare an empty list to store labels
data = []

# Label real frames (0)
for folder in os.listdir(real_dir):
    frame_dir = os.path.join(real_dir, folder)
    if os.path.isdir(frame_dir):
        for frame in os.listdir(frame_dir):
            if frame.endswith('.jpg'):
                data.append([os.path.join(frame_dir, frame), 0])

# Label fake frames (1)
for folder in os.listdir(fake_dir):
    frame_dir = os.path.join(fake_dir, folder)
    if os.path.isdir(frame_dir):
        for frame in os.listdir(frame_dir):
            if frame.endswith('.jpg'):
                data.append([os.path.join(frame_dir, frame), 1])

# Convert to a DataFrame and save as CSV
df = pd.DataFrame(data, columns=['frame_path', 'label'])
df.to_csv('/content/drive/MyDrive/frame_labels_final.csv', index=False)

print("Labeling complete! CSV saved at /content/drive/MyDrive/frame_labels_final.csv")
