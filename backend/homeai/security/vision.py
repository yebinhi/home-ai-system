"""Opt-in cloud event-snapshot analysis; intentionally not called by the webhook.

The supplied bytes must come from an authenticated, authorised Protect event snapshot.
A camera API client, permission checks and retention policy must be implemented before
connecting this to the event pipeline. Do not send continuous video or recognize faces.
"""
import base64
import json
from dataclasses import dataclass
from ..config import get_settings

MAX_IMAGE_BYTES = 3_000_000


@dataclass(frozen=True)
class VisionDecision:
    description: str
    relevant: bool
    confidence: float | None = None


async def analyze_snapshot(image_bytes: bytes, media_type: str = "image/jpeg") -> VisionDecision:
    cfg = get_settings()
    if not cfg.vision_enabled or not cfg.openai_api_key:
        raise PermissionError("Cloud vision requires explicit VISION_ENABLED and OPENAI_API_KEY")
    if media_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Only JPEG, PNG, and WebP snapshots are accepted")
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Snapshot is empty or exceeds the 3 MB limit")

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=cfg.openai_api_key)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    response = await client.responses.create(
        model=cfg.openai_model,
        max_output_tokens=220,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": (
                "Describe only directly visible security-relevant activity in this one home camera "
                "snapshot. Do not identify people, guess identity or sensitive characteristics. "
                "Do not make claims about actions outside this frame. "
                "Return only a JSON object with keys description (string) and relevant (boolean)."
            )},
            {"type": "input_image", "image_url": f"data:{media_type};base64,{encoded}"},
        ]}],
    )
    # If the provider does not return parseable JSON, do not invent a classification.
    raw = response.output_text.strip()
    result = json.loads(raw)
    if not isinstance(result.get("description"), str) or not isinstance(result.get("relevant"), bool):
        raise ValueError("Vision provider returned an invalid structured result")
    return VisionDecision(description=result["description"][:500], relevant=result["relevant"])
