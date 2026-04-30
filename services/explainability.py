from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf


def gradcam_status(model_folder):
    keras_models = sorted(Path(model_folder).glob("*.keras")) + sorted(Path(model_folder).glob("*.h5"))
    if not keras_models:
        return {
            "available": False,
            "status": "needs_keras_model",
            "message": "Grad-CAM requires a .keras or .h5 model. Only TFLite artifacts are present.",
        }
    return {
        "available": True,
        "status": "keras_model_ready",
        "message": f"Grad-CAM can use {keras_models[0].name}.",
        "model_path": str(keras_models[0]),
    }


def generate_gradcam_overlay(model_path, frame, output_path):
    model = tf.keras.models.load_model(model_path)
    last_conv = None
    for layer in reversed(model.layers):
        if len(getattr(layer.output, "shape", [])) == 4:
            last_conv = layer.name
            break

    if last_conv is None:
        raise ValueError("Could not find a convolutional layer for Grad-CAM.")

    grad_model = tf.keras.models.Model(
        [model.inputs],
        [model.get_layer(last_conv).output, model.output],
    )

    input_tensor = np.expand_dims(frame / 255.0, axis=0).astype(np.float32)
    with tf.GradientTape() as tape:
        conv_output, predictions = grad_model(input_tensor)
        loss = predictions[:, 0]
    gradients = tape.gradient(loss, conv_output)
    pooled = tf.reduce_mean(gradients, axis=(0, 1, 2))
    heatmap = tf.reduce_sum(tf.multiply(pooled, conv_output[0]), axis=-1)
    heatmap = np.maximum(heatmap, 0)
    heatmap = heatmap / (np.max(heatmap) + 1e-8)
    heatmap = cv2.resize(heatmap.numpy(), (frame.shape[1], frame.shape[0]))
    heatmap = np.uint8(255 * heatmap)
    heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(frame, 0.6, heatmap, 0.4, 0)
    cv2.imwrite(str(output_path), overlay)
    return str(output_path)
