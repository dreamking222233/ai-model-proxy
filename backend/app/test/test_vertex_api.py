"""Manual Vertex AI Imagen generation test using the official google-genai SDK.

This variant uses Vertex AI with an API key, which matches the credential type
the user provided. It follows the same Imagen model family shown in the console
sample, but uses the newer SDK path that actually supports API key auth.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from google import genai
from google.genai import types


PROJECT_ID = "gen-lang-client-0253039848"
LOCATION = "us-central1"
MODEL_NAME = "imagen-4.0-generate-001"
API_KEY = os.getenv("VERTEX_API_KEY", "")
PROMPT = "生成一张未来感十足的城市夜景海报，霓虹灯、雨夜街道、电影感构图"
ASPECT_RATIO = "1:1"
OUTPUT_DIR = Path("backend/app/test/output")


def main() -> None:
    if not API_KEY:
        raise RuntimeError("Set VERTEX_API_KEY before running this manual test")

    client = genai.Client(
        vertexai=True,
        api_key=API_KEY,
    )

    print(f"Project: {PROJECT_ID} (bound by API key / reference config)")
    print(f"Location: {LOCATION} (model region reference)")
    print(f"Model: {MODEL_NAME}")
    print(f"Prompt: {PROMPT}")

    response = client.models.generate_images(
        model=MODEL_NAME,
        prompt=PROMPT,
        config=types.GenerateImagesConfig(
            numberOfImages=1,
            aspectRatio=ASPECT_RATIO,
            negativePrompt="",
            personGeneration=types.PersonGeneration.ALLOW_ALL,
            safetyFilterLevel=types.SafetyFilterLevel.BLOCK_MEDIUM_AND_ABOVE,
            addWatermark=True,
            outputMimeType="image/png",
        ),
    )

    generated_images = response.generated_images or []
    if not generated_images or not generated_images[0].image or not generated_images[0].image.image_bytes:
        raise RuntimeError(f"Vertex returned no image bytes: {response}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    output_file = OUTPUT_DIR / f"vertex_imagen_{timestamp}.png"
    output_file.write_bytes(generated_images[0].image.image_bytes)

    print("Request succeeded.")
    print(f"Saved file: {output_file}")


if __name__ == "__main__":
    main()
