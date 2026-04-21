"""Helpers for Google Vertex AI image channels."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.core.exceptions import ServiceException
from app.services.channel_service import ChannelService

logger = logging.getLogger(__name__)

_VERTEX_DEFAULT_BASE_URL = "https://aiplatform.googleapis.com"


class GoogleVertexImageService:
    """Encapsulate Vertex SDK loading, routing, and response parsing."""

    @staticmethod
    def resolve_provider_variant(channel) -> str:
        return ChannelService._normalize_provider_variant(
            getattr(channel, "protocol_type", None),
            getattr(channel, "provider_variant", None),
        )

    @staticmethod
    def is_vertex_channel(channel) -> bool:
        return (
            GoogleVertexImageService.resolve_provider_variant(channel)
            == ChannelService.PROVIDER_VARIANT_GOOGLE_VERTEX_IMAGE
        )

    @staticmethod
    def default_vertex_base_url() -> str:
        return _VERTEX_DEFAULT_BASE_URL

    @staticmethod
    def parse_model_candidates(actual_model_name: Optional[str]) -> list[str]:
        raw = str(actual_model_name or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split("|") if item and item.strip()]

    @staticmethod
    def is_imagen_model(model_name: Optional[str]) -> bool:
        return str(model_name or "").strip().lower().startswith("imagen-")

    @staticmethod
    def looks_like_image_model(model_name: Optional[str]) -> bool:
        normalized = str(model_name or "").strip().lower()
        return "image" in normalized or normalized.startswith("imagen-")

    @staticmethod
    def _load_google_genai_modules():
        try:
            from google import genai
            from google.genai import types
            return genai, types
        except ImportError as exc:
            raise ServiceException(
                503,
                "Vertex 图片渠道依赖未安装，请先安装 google-genai",
                "VERTEX_IMAGE_DEPENDENCY_MISSING",
            ) from exc

    @staticmethod
    def _build_imagen_config(types_module, aspect_ratio: Optional[str], image_size: Optional[str]):
        config_kwargs: dict[str, Any] = {
            "numberOfImages": 1,
            "negativePrompt": "",
            "addWatermark": True,
            "outputMimeType": "image/png",
        }
        if aspect_ratio:
            config_kwargs["aspectRatio"] = aspect_ratio
        if image_size:
            config_kwargs["imageSize"] = image_size

        try:
            person_generation = getattr(types_module, "PersonGeneration", None)
            if person_generation is not None and hasattr(person_generation, "ALLOW_ALL"):
                config_kwargs["personGeneration"] = person_generation.ALLOW_ALL
            safety_filter = getattr(types_module, "SafetyFilterLevel", None)
            if safety_filter is not None and hasattr(safety_filter, "BLOCK_MEDIUM_AND_ABOVE"):
                config_kwargs["safetyFilterLevel"] = safety_filter.BLOCK_MEDIUM_AND_ABOVE
            return types_module.GenerateImagesConfig(**config_kwargs)
        except TypeError:
            if "imageSize" in config_kwargs:
                image_size_value = config_kwargs.pop("imageSize")
                config_kwargs["image_size"] = image_size_value
                try:
                    return types_module.GenerateImagesConfig(**config_kwargs)
                except TypeError:
                    config_kwargs.pop("image_size", None)
            # Some SDK versions may not expose imageSize yet; fall back while preserving generation availability.
            return types_module.GenerateImagesConfig(**config_kwargs)

    @staticmethod
    def _build_gemini_config(types_module, aspect_ratio: Optional[str], image_size: Optional[str]):
        config_kwargs: dict[str, Any] = {
            "response_modalities": ["TEXT", "IMAGE"],
        }
        image_config = None
        if aspect_ratio:
            image_config_class = getattr(types_module, "ImageConfig", None)
            if image_config_class is not None:
                image_config = image_config_class(aspectRatio=aspect_ratio)
            else:
                image_config = {"aspectRatio": aspect_ratio}
        if image_config:
            config_kwargs["imageConfig"] = image_config

        try:
            return types_module.GenerateContentConfig(**config_kwargs)
        except TypeError:
            if "imageConfig" in config_kwargs:
                image_config_value = config_kwargs.pop("imageConfig")
                config_kwargs["image_config"] = image_config_value
                try:
                    return types_module.GenerateContentConfig(**config_kwargs)
                except TypeError:
                    config_kwargs.pop("image_config", None)
            return types_module.GenerateContentConfig(**config_kwargs)

    @staticmethod
    def _parse_imagen_response(response) -> tuple[list[dict], Optional[str]]:
        images: list[dict] = []
        generated_images = getattr(response, "generated_images", None) or []
        import base64

        for item in generated_images:
            image_obj = getattr(item, "image", None)
            image_bytes = getattr(image_obj, "image_bytes", None)
            if not image_bytes:
                continue
            mime_type = getattr(image_obj, "mime_type", None) or "image/png"
            images.append({
                "b64_json": base64.b64encode(image_bytes).decode("utf-8"),
                "mime_type": mime_type,
            })
        return images, None

    @staticmethod
    def _parse_gemini_response(response) -> tuple[list[dict], Optional[str]]:
        images: list[dict] = []
        text_output: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        import base64

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    text_output.append(str(part_text))
                inline_data = getattr(part, "inline_data", None)
                data = getattr(inline_data, "data", None) if inline_data is not None else None
                if data:
                    mime_type = getattr(inline_data, "mime_type", None) or "image/png"
                    images.append({
                        "b64_json": base64.b64encode(data).decode("utf-8"),
                        "mime_type": mime_type,
                    })
        return images, "\n".join(text_output).strip() or None

    @staticmethod
    def _generate_images_sync(
        api_key: str,
        candidate_models: list[str],
        prompt: str,
        aspect_ratio: Optional[str],
        image_size: Optional[str],
    ) -> tuple[list[dict], Optional[str], str]:
        genai, types_module = GoogleVertexImageService._load_google_genai_modules()
        client = genai.Client(vertexai=True, api_key=api_key)
        last_error: Exception | None = None

        for candidate_model in candidate_models:
            try:
                if GoogleVertexImageService.is_imagen_model(candidate_model):
                    response = client.models.generate_images(
                        model=candidate_model,
                        prompt=prompt,
                        config=GoogleVertexImageService._build_imagen_config(
                            types_module,
                            aspect_ratio,
                            image_size,
                        ),
                    )
                    images, extra_text = GoogleVertexImageService._parse_imagen_response(response)
                else:
                    response = client.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                        config=GoogleVertexImageService._build_gemini_config(
                            types_module,
                            aspect_ratio,
                            image_size,
                        ),
                    )
                    images, extra_text = GoogleVertexImageService._parse_gemini_response(response)

                if images:
                    return images, extra_text, candidate_model
                last_error = ServiceException(
                    503,
                    f"Vertex model '{candidate_model}' returned no image data",
                    "VERTEX_IMAGE_GENERATION_FAILED",
                )
            except ServiceException as exc:
                last_error = exc
            except Exception as exc:
                logger.warning("Vertex image candidate %s failed: %s", candidate_model, exc)
                last_error = ServiceException(
                    400,
                    f"Vertex image generation failed on model '{candidate_model}': {exc}",
                    "VERTEX_IMAGE_GENERATION_FAILED",
                )

        if isinstance(last_error, ServiceException):
            raise last_error
        raise ServiceException(
            503,
            "Vertex image generation returned no image data",
            "VERTEX_IMAGE_GENERATION_FAILED",
        )

    @staticmethod
    async def generate_images(
        api_key: str,
        actual_model_name: str,
        prompt: str,
        aspect_ratio: Optional[str] = None,
        image_size: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str], str]:
        candidate_models = GoogleVertexImageService.parse_model_candidates(actual_model_name)
        if not candidate_models:
            raise ServiceException(400, "Missing Vertex actual model mapping", "VERTEX_IMAGE_MODEL_NOT_CONFIGURED")
        return await asyncio.to_thread(
            GoogleVertexImageService._generate_images_sync,
            api_key,
            candidate_models,
            prompt,
            aspect_ratio,
            image_size,
        )

    @staticmethod
    def _health_check_sync(api_key: str, model_name: str) -> None:
        genai, _types_module = GoogleVertexImageService._load_google_genai_modules()
        client = genai.Client(vertexai=True, api_key=api_key)
        client.models.generate_content(
            model=model_name,
            contents="Reply with OK only.",
        )

    @staticmethod
    async def health_check(api_key: str, model_name: str) -> None:
        candidate_models = GoogleVertexImageService.parse_model_candidates(model_name)
        if not candidate_models:
            raise ServiceException(400, "Missing Vertex health check model", "VERTEX_HEALTH_CHECK_MODEL_MISSING")
        await asyncio.to_thread(
            GoogleVertexImageService._health_check_sync,
            api_key,
            candidate_models[0],
        )
