"""
Hugging Face FLUX.1-schnell image generation client.
Uses huggingface_hub InferenceClient with fal-ai provider.
Used for: recipe images, product blueprint visuals, food item thumbnails.
"""
import io
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Best available models in order of preference
MODELS = [
    "black-forest-labs/FLUX.1-schnell",  # Fastest, 1-4 steps
    "black-forest-labs/FLUX.1-dev",      # Higher quality
    "stabilityai/stable-diffusion-xl-base-1.0",  # Fallback
]


def _get_client():
    """Get HF InferenceClient. Returns None if token not set."""
    if not HF_TOKEN:
        return None
    try:
        from huggingface_hub import InferenceClient
        return InferenceClient(api_key=HF_TOKEN)
    except Exception as exc:
        logger.error("Failed to create HF client: %s", exc)
        return None


def _generate_sync(prompt: str, width: int, height: int, steps: int) -> Optional[bytes]:
    """Synchronous image generation — runs in thread pool."""
    client = _get_client()
    if not client:
        return None

    for model in MODELS:
        try:
            logger.info("Generating image with %s: %s", model, prompt[:60])
            image = client.text_to_image(
                prompt,
                model=model,
                width=width,
                height=height,
                num_inference_steps=steps,
            )
            # image is a PIL.Image object
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            img_bytes = buf.read()
            logger.info("Image generated: %d bytes", len(img_bytes))
            return img_bytes

        except Exception as exc:
            err = str(exc).lower()
            if "loading" in err or "503" in err:
                logger.info("Model %s loading, trying next...", model)
                continue
            elif "429" in err or "rate" in err:
                logger.warning("Rate limit hit on %s", model)
                return None
            else:
                logger.warning("Model %s failed: %s", model, exc)
                continue

    return None


async def generate_image(
    prompt: str,
    width: int = 512,
    height: int = 512,
    num_inference_steps: int = 4,
) -> Optional[bytes]:
    """Async wrapper — runs sync HF client in thread pool."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _generate_sync, prompt, width, height, num_inference_steps
    )


async def generate_recipe_image(recipe_name: str, cuisine: str = "") -> Optional[bytes]:
    """Generate an appetizing food photo for a recipe."""
    cuisine_hint = f"{cuisine} " if cuisine else ""
    prompt = (
        f"Professional food photography of {recipe_name}, {cuisine_hint}cuisine, "
        f"beautifully plated on a clean white plate, soft natural lighting, "
        f"shallow depth of field, restaurant quality, appetizing, high resolution, "
        f"food blog style, warm tones"
    )
    return await generate_image(prompt, width=512, height=512, num_inference_steps=4)


async def generate_food_item_image(item_name: str, category: str = "") -> Optional[bytes]:
    """Generate a clean product/food image for an inventory item."""
    prompt = (
        f"Clean product photo of fresh {item_name}, {category} food, "
        f"white background, studio lighting, sharp focus, minimal composition, "
        f"supermarket product style, high quality photography"
    )
    return await generate_image(prompt, width=256, height=256, num_inference_steps=4)


async def generate_blueprint_image(product_name: str, redesign_spec: str = "") -> Optional[bytes]:
    """
    Generate an accurate new product concept image using FLUX.
    Uses K2-Think to first build a detailed visual spec, then feeds it to FLUX.
    """
    # Step 1: Use K2 to generate a precise visual description of the new product
    if not redesign_spec:
        try:
            from fridge_observer.ai_client import k2_chat, ANSWER_SEP
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a product designer specialising in sustainable packaging. "
                        "Generate a precise visual description for an AI image generator. "
                        "Be extremely specific about: shape, materials, colors, labels, textures, dimensions. "
                        "Output ONLY the image prompt after the separator, no explanation.\n\n"
                        f"FORMAT: {ANSWER_SEP}\n[image prompt only]"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create a detailed image generation prompt for a NEW sustainable version of: {product_name}\n\n"
                        "The new product should use eco-friendly materials (recycled/biodegradable packaging), "
                        "have a modern minimal design, clear sustainability labels, and look like a real "
                        "premium product you'd find in a health food store. "
                        "Describe exactly what it looks like visually for an AI image generator. "
                        "Include: packaging type, shape, primary color, material texture, label design, "
                        "any eco certifications shown, overall aesthetic. "
                        "Keep the prompt under 120 words."
                    ),
                },
            ]
            response = await k2_chat(messages, stream=False)
            if ANSWER_SEP in response:
                redesign_spec = response.rsplit(ANSWER_SEP, 1)[1].strip()
            else:
                paragraphs = [p.strip() for p in response.strip().split("\n\n") if p.strip()]
                redesign_spec = paragraphs[-1] if paragraphs else ""
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("K2 spec generation failed: %s", exc)

    # Step 2: Build the final FLUX prompt
    if redesign_spec and len(redesign_spec) > 20:
        prompt = (
            f"{redesign_spec}, "
            f"product photography, white background, studio lighting, "
            f"sharp focus, professional product shot, 4K, photorealistic"
        )
    else:
        # Fallback to a detailed generic prompt
        prompt = (
            f"New sustainable eco-friendly version of {product_name}, "
            f"biodegradable packaging made from recycled kraft paper and plant-based materials, "
            f"minimalist modern label design with green leaf logo and recycling symbols, "
            f"earthy natural color palette of sage green and cream white, "
            f"premium health food store aesthetic, "
            f"product photography on white background, studio lighting, sharp focus, photorealistic, 4K"
        )

    return await generate_image(prompt, width=768, height=768, num_inference_steps=4)


def image_to_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Convert image bytes to a base64 data URL."""
    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"
