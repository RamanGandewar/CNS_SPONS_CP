# Auto-exported from CSI_3.ipynb

from google.colab import drive
drive.mount('/content/drive')

# %%

import os
import cv2
import random
import numpy as np
import pickle
from tqdm import tqdm
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# %%

# Paths to dataset folders
DATASET_DIR = "/content/drive/MyDrive/FOR_DATASET_0/DATASET_0"
REAL_DIR = os.path.join(DATASET_DIR, "REAL")
SYNTHESIS_DIR = os.path.join(DATASET_DIR, "FAKE")

# Parameters
FRAME_RATE = 1
FRAME_SIZE = (224, 224)
AUGMENTATION = True

# %%

def extract_limited_frames(video_path, output_dir, max_frames=20, frame_size=(224, 224)):

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

    os.makedirs(output_dir, exist_ok=True)

    for video in tqdm(os.listdir(input_dir), desc=f"Processing videos in {input_dir}"):
        if video.endswith(".mp4"):
            video_path = os.path.join(input_dir, video)
            video_output_dir = os.path.join(output_dir, os.path.splitext(video)[0])
            extract_limited_frames(video_path, video_output_dir, max_frames, frame_size)

# Paths
REAL_DIR = "/content/drive/MyDrive/FOR_DATASET_0/DATASET_0/REAL"
SYNTHESIS_DIR = "/content/drive/MyDrive/FOR_DATASET_0/DATASET_0/FAKE"
OUTPUT_DIR = "/content/drive/MyDrive/FOR_DATASET_0/frames_1"

# Extract frames for real and synthesized videos
process_videos_limited_frames(REAL_DIR, os.path.join(OUTPUT_DIR, "REAL"))
process_videos_limited_frames(SYNTHESIS_DIR, os.path.join(OUTPUT_DIR, "FAKE"))

# %%

import os
import cv2
import pandas as pd
from tqdm import tqdm

def detect_and_save_faces(frame, frame_filename, face_cascade):

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Convert to grayscale for face detection
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) > 0:
        cv2.imwrite(frame_filename, frame)  # Save frame if faces are detected
        return True
    return False

def extract_faces_and_save_csv(video_dir, output_dir, label, csv_path, max_frames=20, frame_size=(224, 224)):

    os.makedirs(output_dir, exist_ok=True)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    data = []

    for video in tqdm(os.listdir(video_dir), desc=f"Processing {video_dir}"):
        if video.endswith(".mp4"):
            video_path = os.path.join(video_dir, video)
            video_output_dir = os.path.join(output_dir, os.path.splitext(video)[0])
            os.makedirs(video_output_dir, exist_ok=True)

            cap = cv2.VideoCapture(video_path)
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(min(cap.get(cv2.CAP_PROP_FRAME_COUNT), fps * 10))
            frame_interval = max(total_frames // max_frames, 1)

            frame_count = 0
            saved_frames = 0

            while saved_frames < max_frames:
                ret, frame = cap.read()
                if not ret or frame_count >= total_frames:
                    break

                if frame_count % frame_interval == 0:
                    frame = cv2.resize(frame, frame_size)
                    frame_filename = os.path.join(video_output_dir, f"frame_{saved_frames:04d}.jpg")

                    if detect_and_save_faces(frame, frame_filename, face_cascade):
                        data.append({"frame_path": frame_filename, "label": label})
                        saved_frames += 1
                frame_count += 1

            cap.release()

    # Append data to CSV
    if os.path.exists(csv_path):
        existing_df = pd.read_csv(csv_path)
        new_df = pd.DataFrame(data)
        df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        df = pd.DataFrame(data)

    df.to_csv(csv_path, index=False)
    print(f"Saved data to {csv_path}")

# Paths
REAL_DIR = "/content/drive/MyDrive/FOR_DATASET_0/DATASET_0/REAL"
SYNTHESIS_DIR = "/content/drive/MyDrive/FOR_DATASET_0/DATASET_0/FAKE"
OUTPUT_DIR = "/content/drive/MyDrive/FOR_DATASET_0/frames_3"
CSV_PATH = "/content/drive/MyDrive/FOR_DATASET_0/labels_3.csv"

# Process real and synthesized videos
extract_faces_and_save_csv(REAL_DIR, os.path.join(OUTPUT_DIR, "REAL"), label=0, csv_path=CSV_PATH, max_frames=30)
extract_faces_and_save_csv(SYNTHESIS_DIR, os.path.join(OUTPUT_DIR, "FAKE"), label=1, csv_path=CSV_PATH, max_frames=30)

# %%

import pandas as pd
CSV_PATH = "/content/drive/MyDrive/FOR_DATASET_0/labels_3.csv"
df = pd.read_csv(CSV_PATH)
df.shape
