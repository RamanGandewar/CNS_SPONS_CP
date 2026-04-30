# Auto-exported from CSI_4.ipynb

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

import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D, Input
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import pandas as pd
import numpy as np
import os

# %%

import pandas as pd
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Load CSV file containing frame paths and labels
csv_path = "/content/drive/MyDrive/FOR_DATASET_0/labels_3.csv"
df = pd.read_csv(csv_path)

desired_size = 10000
df_reduced = df.groupby("label", group_keys=False).apply(
    lambda x: x.sample(int(desired_size * len(x) / len(df)), random_state=101)
)

# Split data into training and validation sets
train_df, temp_df = train_test_split(df_reduced, test_size=0.2, stratify=df_reduced["label"], random_state=101)
val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df["label"], random_state=101)

# Convert label column to strings
train_df["label"] = train_df["label"].astype(str)
val_df["label"] = val_df["label"].astype(str)
test_df["label"] = test_df["label"].astype(str)

# Ensure ImageDataGenerators are properly defined
train_datagen = ImageDataGenerator(rescale=1.0/255.0)
val_datagen = ImageDataGenerator(rescale=1.0/255.0)

# Define ImageDataGenerators
train_generator = train_datagen.flow_from_dataframe(
    train_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

val_generator = val_datagen.flow_from_dataframe(
    val_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

print("Training Labels Distribution:")
print(train_df["label"].value_counts())

print("\nValidation Labels Distribution:")
print(val_df["label"].value_counts())

print("\nTest Labels Distribution:")
print(test_df["label"].value_counts())

# %%

# Load the MobileNetV2 model with pre-trained weights
base_model = MobileNetV2(weights="imagenet", include_top=False, input_tensor=Input(shape=(224, 224, 3)))

# Freeze the base model
base_model.trainable = False

# Add custom layers
x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.3)(x)
x = Dense(128, activation="relu")(x)
x = Dropout(0.3)(x)
output = Dense(1, activation="sigmoid")(x)  # Binary classification

model0 = Model(inputs=base_model.input, outputs=output)

# %%

# Compile the model
model0.compile(optimizer=Adam(learning_rate=0.002), loss="binary_crossentropy", metrics=["accuracy"])

# %%

# Early stopping and checkpointing
early_stopping = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss", patience=3, restore_best_weights=True
)
model_checkpoint = tf.keras.callbacks.ModelCheckpoint(
    "best_model_3.keras",  # Change the extension to `.keras`
    monitor="val_accuracy",
    save_best_only=True,
    verbose=1
)

# Train the model
history = model0.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,
    callbacks=[early_stopping, model_checkpoint]
)

# %%

base_model.trainable = True
for layer in base_model.layers[:-20]:  # Keep earlier layers frozen
    layer.trainable = False

# %%

model0.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0002),
    loss='binary_crossentropy',
    metrics=['accuracy']
)

# %%

history_finetune = model0.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,
    callbacks=[early_stopping, model_checkpoint]
)

# %%

test_datagen = ImageDataGenerator(rescale=1.0/255.0)
test_generator = test_datagen.flow_from_dataframe(
    test_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

# %%

test_loss, test_accuracy = model0.evaluate(test_generator, steps=len(test_generator))
print(f"Test Loss: {test_loss}")
print(f"Test Accuracy: {test_accuracy}")

# %%

MODEL_SAVE_PATH = '/content/drive/MyDrive/FOR_DATASET_0/deepfake_detector_model_3.h5'
model0.save(MODEL_SAVE_PATH)
print(f"Model saved at {MODEL_SAVE_PATH}")

# %%

import tensorflow as tf

# ... your existing code ...

# Convert the Keras model to TensorFlow Lite
converter = tf.lite.TFLiteConverter.from_keras_model(model0)
tflite_model = converter.convert()

# Save the TensorFlow Lite model
TFLITE_MODEL_PATH = '/content/drive/MyDrive/FOR_DATASET_0/deepfake_detector_model_3.tflite'
with open(TFLITE_MODEL_PATH, 'wb') as f:
    f.write(tflite_model)
print(f"TFLite model saved at {TFLITE_MODEL_PATH}")

# %%

import pandas as pd
import tensorflow as tf
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.layers import GlobalAveragePooling2D, Dropout, Dense, Input
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split

# %%

# Load CSV file containing frame paths and labels
csv_path = "/content/drive/MyDrive/FOR_DATASET_0/labels_3.csv"
df = pd.read_csv(csv_path)

desired_size = 10000
df_reduced = df.groupby("label", group_keys=False).apply(
    lambda x: x.sample(int(desired_size * len(x) / len(df)), random_state=101)
)

# Split data into training and validation sets
train_df, temp_df = train_test_split(df_reduced, test_size=0.2, stratify=df_reduced["label"], random_state=101)
val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df["label"], random_state=101)

# %%

# Convert label column to strings
train_df["label"] = train_df["label"].astype(str)
val_df["label"] = val_df["label"].astype(str)
test_df["label"] = test_df["label"].astype(str)

# %%

# Ensure ImageDataGenerators are properly defined
train_datagen = ImageDataGenerator(rescale=1.0/255.0)
val_datagen = ImageDataGenerator(rescale=1.0/255.0)

# Define ImageDataGenerators
train_generator = train_datagen.flow_from_dataframe(
    train_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

val_generator = val_datagen.flow_from_dataframe(
    val_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

# %%

print("Training Labels Distribution:")
print(train_df["label"].value_counts())

print("\nValidation Labels Distribution:")
print(val_df["label"].value_counts())

print("\nTest Labels Distribution:")
print(test_df["label"].value_counts())

# %%

# Load the EfficientNetB0 model with pre-trained weights
base_model = EfficientNetB0(weights="imagenet", include_top=False, input_tensor=Input(shape=(224, 224, 3)))

# %%

# Freeze the base model
base_model.trainable = False

# Add custom layers
x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.3)(x)
x = Dense(128, activation="relu")(x)
x = Dropout(0.3)(x)
output = Dense(1, activation="sigmoid")(x)  # Binary classification

model = Model(inputs=base_model.input, outputs=output)

# %%

# Compile the model
model.compile(optimizer=Adam(learning_rate=0.002), loss="binary_crossentropy", metrics=["accuracy"])

# Early stopping and checkpointing
early_stopping = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss", patience=3, restore_best_weights=True
)
model_checkpoint = tf.keras.callbacks.ModelCheckpoint(
    "best_model_efficientnet.keras",  # Change the extension to `.keras`
    monitor="val_accuracy",
    save_best_only=True,
    verbose=1
)

# %%

# Train the model
history = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,
    callbacks=[early_stopping, model_checkpoint]
)

# %%

base_model.trainable = True
for layer in base_model.layers[:-20]:  # Keep earlier layers frozen
    layer.trainable = False

# %%

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0002),
    loss='binary_crossentropy',
    metrics=['accuracy']
)

# %%

history_finetune = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,
    callbacks=[early_stopping, model_checkpoint]
)

# %%

test_datagen = ImageDataGenerator(rescale=1.0/255.0)
test_generator = test_datagen.flow_from_dataframe(
    test_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

# %%

test_loss, test_accuracy = model.evaluate(test_generator, steps=len(test_generator))
print(f"Test Loss: {test_loss}")
print(f"Test Accuracy: {test_accuracy}")

# %%

import os
import cv2
import random
import numpy as np
import pickle
from tqdm import tqdm
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# %%

import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D, Input
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import pandas as pd

# %%

import pandas as pd
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Load CSV file containing frame paths and labels
csv_path = "/content/drive/MyDrive/FOR_DATASET_0/labels_3.csv"
df = pd.read_csv(csv_path)

desired_size = 11300
df_reduced = df.groupby("label", group_keys=False).apply(
    lambda x: x.sample(int(desired_size * len(x) / len(df)), random_state=101)
)

# Split data into training and validation sets
train_df, temp_df = train_test_split(df_reduced, test_size=0.2, stratify=df_reduced["label"], random_state=101)
val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df["label"], random_state=101)

# Convert label column to strings
train_df["label"] = train_df["label"].astype(str)
val_df["label"] = val_df["label"].astype(str)
test_df["label"] = test_df["label"].astype(str)

# Ensure ImageDataGenerators are properly defined
train_datagen = ImageDataGenerator(rescale=1.0/255.0)
val_datagen = ImageDataGenerator(rescale=1.0/255.0)

# Define ImageDataGenerators
train_generator = train_datagen.flow_from_dataframe(
    train_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

val_generator = val_datagen.flow_from_dataframe(
    val_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

print("Training Labels Distribution:")
print(train_df["label"].value_counts())

print("\nValidation Labels Distribution:")
print(val_df["label"].value_counts())

print("\nTest Labels Distribution:")
print(test_df["label"].value_counts())

# %%

# Load the MobileNetV2 model with pre-trained weights
base_model = MobileNetV2(weights="imagenet", include_top=False, input_tensor=Input(shape=(224, 224, 3)))

# Freeze the base model
base_model.trainable = False

# Add custom layers
x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.3)(x)
x = Dense(128, activation="relu")(x)
x = Dropout(0.3)(x)
output = Dense(1, activation="sigmoid")(x)  # Binary classification

model0 = Model(inputs=base_model.input, outputs=output)

# %%

# Compile the model
model0.compile(optimizer=Adam(learning_rate=0.002), loss="binary_crossentropy", metrics=["accuracy"])

# %%

history = model0.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,
)

# %%

base_model.trainable = True
for layer in base_model.layers[:-20]:  # Keep earlier layers frozen
    layer.trainable = False

# %%

model0.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0002),
    loss='binary_crossentropy',
    metrics=['accuracy']
)

# %%

history_finetune = model0.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,
)

# %%

test_datagen = ImageDataGenerator(rescale=1.0/255.0)
test_generator = test_datagen.flow_from_dataframe(
    test_df,
    x_col="frame_path",
    y_col="label",
    target_size=(224, 224),
    batch_size=32,
    class_mode="binary"
)

# %%

val_loss, val_accuracy = model0.evaluate(val_generator, steps=len(val_generator))
print(f"Validation Loss: {val_loss}")
print(f"Validation Accuracy: {val_accuracy}")

# %%

test_loss, test_accuracy = model0.evaluate(test_generator, steps=len(test_generator))
print(f"Test Loss: {test_loss}")
print(f"Test Accuracy: {test_accuracy}")

# %%

MODEL_SAVE_PATH = '/content/drive/MyDrive/deepfake_detector_model_final.h5'
model0.save(MODEL_SAVE_PATH)
print(f"Model saved at {MODEL_SAVE_PATH}")
converter = tf.lite.TFLiteConverter.from_keras_model(model0)
tflite_model = converter.convert()
TFLITE_MODEL_PATH = '/content/drive/MyDrive/deepfake_detector_model_final.tflite'
with open(TFLITE_MODEL_PATH, 'wb') as f:
    f.write(tflite_model)
print(f"TFLite model saved at {TFLITE_MODEL_PATH}")

# %%

val_generator.reset()
predictions = (model0.predict(val_generator) > 0.5).astype(int).flatten()
true_labels = val_generator.classes

# %%

import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
cm = confusion_matrix(true_labels, predictions)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Real', 'Deepfake'], yticklabels=['Real', 'Deepfake'])
plt.title('Confusion Matrix')
plt.xlabel('Predicted')
plt.ylabel('True')
plt.show()

# %%

report = classification_report(true_labels, predictions, target_names=['Real', 'Deepfake'])
print("Classification Report:\n", report)

# %%

test_generator.reset()
predictions = (model0.predict(test_generator) > 0.5).astype(int).flatten()
true_labels = test_generator.classes

# %%

import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
cm = confusion_matrix(true_labels, predictions)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Real', 'Deepfake'], yticklabels=['Real', 'Deepfake'])
plt.title('Confusion Matrix')
plt.xlabel('Predicted')
plt.ylabel('True')
plt.show()

# %%

report = classification_report(true_labels, predictions, target_names=['Real', 'Deepfake'])
print("Classification Report:\n", report)

# %%

plt.figure(figsize=(12, 4))
plt.subplot(1, 2, 1)
plt.plot(history.history['loss'], label='Training Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.title('Loss Over Epochs')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.legend()

# %%

plt.figure(figsize=(12, 4))
plt.subplot(1, 2, 2)
plt.plot(history.history['accuracy'], label='Training Accuracy')
plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
plt.title('Accuracy Over Epochs')
plt.xlabel('Epochs')
plt.ylabel('Accuracy')
plt.legend()
