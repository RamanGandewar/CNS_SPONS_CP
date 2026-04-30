# Auto-exported from CSI_1.ipynb

from google.colab import drive
drive.mount('/content/drive')

# %%

import os
import pandas as pd

# Define paths
base_dir = '/content/drive/MyDrive/dataset_frames_2'
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
df.to_csv('/content/drive/MyDrive/labels_frames_4.csv', index=False)

print("Labeling complete! CSV saved at /content/drive/MyDrive/labels_frames_4.csv")

# %%

import os
import pandas as pd
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout, BatchNormalization, concatenate
from tensorflow.keras.layers import GlobalMaxPooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam

# %%

BATCH_SIZE = 32
IMG_SIZE = (224, 224)
EPOCHS = 10
LEARNING_RATE = 0.001

# %%

csv_path = "/content/drive/MyDrive/labels_frames_4.csv"
base_dir = "/content/drive/MyDrive/dataset_frames_2"

data = pd.read_csv(csv_path)

# %%

train_data = data.sample(frac=0.7, random_state=42)  # 70% for training
val_data = data.drop(train_data.index)  # Remaining 30% for validation

# %%

train_datagen = ImageDataGenerator(rescale=1.0/255.0, horizontal_flip=True, rotation_range=20)
val_datagen = ImageDataGenerator(rescale=1.0/255.0)

# %%

# Convert labels to strings
train_data['label'] = train_data['label'].astype(str)
val_data['label'] = val_data['label'].astype(str)

train_generator = train_datagen.flow_from_dataframe(
    train_data,
    x_col="frame_path",
    y_col="label",
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="binary"
)

val_generator = val_datagen.flow_from_dataframe(
    val_data,
    x_col="frame_path",
    y_col="label",
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="binary"
)

# %%

base_model = MobileNetV2(input_shape=IMG_SIZE + (3,), include_top=False, weights="imagenet")

# %%

base_model.trainable = False

# %%

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(128, activation="relu")(x)
predictions = Dense(1, activation="sigmoid")(x)

# %%

x = base_model.output
avg_pool = GlobalAveragePooling2D()(x)
max_pool = GlobalMaxPooling2D()(x)
x = concatenate([avg_pool, max_pool])

x = Dense(256, activation="relu")(x)
x = BatchNormalization()(x)
x = Dropout(0.4)(x)

x = Dense(128, activation="relu")(x)
x = Dropout(0.3)(x)

predictions = Dense(1, activation="sigmoid")(x)

# %%

#1st trained model on 560 imgs
model = Model(inputs=base_model.input, outputs=predictions)

# %%

#2nd trained model on 798 imgs
model2 = Model(inputs=base_model.input, outputs=predictions)

# %%

#3rd model on 798 imgs
model3 = Model(inputs=base_model.input, outputs=predictions)

# %%

# Compile the model(1st)
model.compile(optimizer=Adam(learning_rate=LEARNING_RATE), loss="binary_crossentropy", metrics=["accuracy"])

# %%

# Compile the model(2nd)
model2.compile(optimizer=Adam(learning_rate=LEARNING_RATE), loss="binary_crossentropy", metrics=["accuracy"])

# %%

# Compile the model(3rd)
model3.compile(optimizer=Adam(learning_rate=LEARNING_RATE), loss="binary_crossentropy", metrics=["accuracy"])

# %%

history_fine = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

# Fine-tuning: Unfreeze some layers of the base model and train further
for layer in base_model.layers[-30:]:  # Unfreeze the last 30 layers
    layer.trainable = True

model.compile(optimizer=Adam(learning_rate=LEARNING_RATE / 10), loss="binary_crossentropy", metrics=["accuracy"])

# Train again for fine-tuning
history_fine = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

#2nd model
history_fine = model2.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

# Fine-tuning: Unfreeze some layers of the base model and train further
for layer in base_model.layers[-30:]:  # Unfreeze the last 30 layers
    layer.trainable = True

model.compile(optimizer=Adam(learning_rate=LEARNING_RATE / 10), loss="binary_crossentropy", metrics=["accuracy"])

# Train again for fine-tuning
history_fine = model2.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

#3rd model
history_fine = model3.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

# Fine-tuning: Unfreeze some layers of the base model and train further
for layer in base_model.layers[-30:]:  # Unfreeze the last 30 layers
    layer.trainable = True

model3.compile(optimizer=Adam(learning_rate=LEARNING_RATE / 10), loss="binary_crossentropy", metrics=["accuracy"])

# Train again for fine-tuning
history_fine = model3.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

# Convert to TensorFlow Lite for mobile integration
converter = tf.lite.TFLiteConverter.from_keras_model(model3)
tflite_model = converter.convert()

# Save the TFLite model
with open("/content/drive/MyDrive/deepfake_detector_model3.tflite", "wb") as f:
    f.write(tflite_model)

print("Model training and conversion completed successfully!")

# %%

val_loss, val_accuracy = model3.evaluate(val_generator, verbose=1)
print(f"Validation Loss: {val_loss}")
print(f"Validation Accuracy: {val_accuracy}")

# %%

# Generate predictions
val_generator.reset()
predictions = model3.predict(val_generator, verbose=1)
predicted_classes = (predictions > 0.5).astype("int32").flatten()
true_classes = val_generator.classes

# %%

# Classification report
# Import the classification_report function
from sklearn.metrics import classification_report

report = classification_report(true_classes, predicted_classes, target_names=["Real", "Deepfake"], digits=4)
print("\nClassification Report:\n", report)

# %%

# Confusion matrix
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

cm = confusion_matrix(true_classes, predicted_classes)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Real", "Deepfake"], yticklabels=["Real", "Deepfake"])
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Confusion Matrix")
plt.show()

# %%

#3rd model on 1862 imgs
model4 = Model(inputs=base_model.input, outputs=predictions)

# %%

# Compile the model(3rd)
model4.compile(optimizer=Adam(learning_rate=LEARNING_RATE), loss="binary_crossentropy", metrics=["accuracy"])

# %%

history_fine = model4.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

# Fine-tuning: Unfreeze some layers of the base model and train further
for layer in base_model.layers[-30:]:  # Unfreeze the last 30 layers
    layer.trainable = True

model4.compile(optimizer=Adam(learning_rate=LEARNING_RATE / 10), loss="binary_crossentropy", metrics=["accuracy"])

# Train again for fine-tuning
history_fine = model4.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    steps_per_epoch=train_generator.n // BATCH_SIZE,
    validation_steps=val_generator.n // BATCH_SIZE
)

# %%

# Convert to TensorFlow Lite for mobile integration
converter = tf.lite.TFLiteConverter.from_keras_model(model4)
tflite_model = converter.convert()

# Save the TFLite model
with open("/content/drive/MyDrive/deepfake_detector_model4.tflite", "wb") as f:
    f.write(tflite_model)

print("Model training and conversion completed successfully!")

# %%

val_loss, val_accuracy = model3.evaluate(val_generator, verbose=1)
print(f"Validation Loss: {val_loss}")
print(f"Validation Accuracy: {val_accuracy}")

# %%

# Generate predictions
val_generator.reset()
predictions = model3.predict(val_generator, verbose=1)
predicted_classes = (predictions > 0.5).astype("int32").flatten()
true_classes = val_generator.classes

# %%

# Classification report
from sklearn.metrics import classification_report

report = classification_report(true_classes, predicted_classes, target_names=["Real", "Deepfake"], digits=4)
print("\nClassification Report:\n", report)

# %%

# Confusion matrix
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

cm = confusion_matrix(true_classes, predicted_classes)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Real", "Deepfake"], yticklabels=["Real", "Deepfake"])
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Confusion Matrix")
plt.show()
