"""Sustainability Blueprint endpoint — food product analysis powered by K2-Think."""
import logging
import json as _json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastapi import Depends
from pydantic import BaseModel
from typing import Optional

from fridge_observer.db import get_db
from fridge_observer.routers.auth_router import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sustainability", tags=["sustainability"])

ANSWER_SEP = "---ANSWER---"

# ── Models ────────────────────────────────────────────────────

class ProductAnalysisRequest(BaseModel):
    product_name: str
    category: Optional[str] = None
    focus: Optional[str] = "full"


# ── Helpers ───────────────────────────────────────────────────

def _extract_answer(text: str) -> str:
    if ANSWER_SEP in text:
        return text.rsplit(ANSWER_SEP, 1)[1].strip()
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    return paragraphs[-1] if paragraphs else text.strip()


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/inventory-items")
async def get_inventory_items(current_user: dict = Depends(get_current_user)):
    from fridge_observer.supabase_client import get_supabase
    sb = get_supabase()
    result = sb.table("food_items").select("id, name, category").eq("user_id", current_user["sub"]).order("name").execute()
    return result.data or []


@router.post("/analyse-product")
async def analyse_product(body: ProductAnalysisRequest):
    """
    Analyse a food product's sustainability using K2-Think.
    Returns structured JSON streamed as SSE — each event is a JSON object
    with a 'section' key so the frontend can render it progressively.
    """
    category_hint = f" (category: {body.category})" if body.category else ""
    focus = body.focus or "full"

    SYSTEM_PROMPT = (
        "You are a sustainability expert and product analyst. "
        "Analyse food and consumer products for environmental impact. "
        "Always respond with ONLY valid JSON — no extra text, no markdown.\n\n"
        f"FORMAT: Write your final JSON after '{ANSWER_SEP}'.\n{ANSWER_SEP}\n{{...}}"
    )

    focus_prompts = {
        "full": f"""Analyse the sustainability of: {body.product_name}{category_hint}

Return a JSON object with exactly these keys:
{{
  "impact_score": <integer 1-10, where 1=very sustainable, 10=very harmful>,
  "co2_per_unit": "<e.g. 3.2 kg CO2 per litre>",
  "water_usage": "<e.g. 628 litres per litre of product>",
  "packaging_rating": "<Excellent|Good|Fair|Poor>",
  "food_miles": "<e.g. ~500km average>",
  "key_facts": ["<fact 1>", "<fact 2>", "<fact 3>"],
  "alternatives": [
    {{"name": "<product name>", "reason": "<why it's better>", "co2_saving": "<e.g. 60% less CO2>"}},
    {{"name": "<product name>", "reason": "<why it's better>", "co2_saving": "<e.g. 40% less CO2>"}},
    {{"name": "<product name>", "reason": "<why it's better>", "co2_saving": "<e.g. 30% less CO2>"}}
  ],
  "blueprint": {{
    "packaging": "<how packaging could be improved>",
    "sourcing": "<how ingredients/sourcing could be improved>",
    "production": "<how production process could be greener>",
    "end_of_life": "<recyclability and disposal improvements>"
  }},
  "verdict": "<2-3 sentence overall sustainability verdict>"
}}""",

        "co2": f"""Analyse the carbon footprint of: {body.product_name}{category_hint}

Return JSON:
{{
  "co2_per_unit": "<e.g. 3.2 kg CO2 per litre>",
  "breakdown": {{
    "production": "<% and kg>",
    "transport": "<% and kg>",
    "packaging": "<% and kg>",
    "retail": "<% and kg>"
  }},
  "vs_average": "<how this compares to category average>",
  "reduction_tips": ["<tip 1>", "<tip 2>", "<tip 3>"],
  "low_carbon_alternative": "<specific product recommendation>"
}}""",

        "alternatives": f"""Suggest sustainable alternatives to: {body.product_name}{category_hint}

Return JSON:
{{
  "alternatives": [
    {{"name": "<product>", "type": "<organic|local|plant-based|recycled-packaging|etc>", "co2_saving": "<e.g. 60% less>", "benefit": "<key environmental benefit>", "where_to_find": "<supermarket/online/local>"}},
    {{"name": "<product>", "type": "<type>", "co2_saving": "<saving>", "benefit": "<benefit>", "where_to_find": "<where>"}},
    {{"name": "<product>", "type": "<type>", "co2_saving": "<saving>", "benefit": "<benefit>", "where_to_find": "<where>"}},
    {{"name": "<product>", "type": "<type>", "co2_saving": "<saving>", "benefit": "<benefit>", "where_to_find": "<where>"}}
  ],
  "best_pick": "<name of the single best alternative and why>"
}}""",

        "blueprint": f"""Create a sustainability redesign blueprint for: {body.product_name}{category_hint}

Return JSON:
{{
  "current_issues": ["<issue 1>", "<issue 2>", "<issue 3>"],
  "redesign": {{
    "packaging": {{"current": "<current packaging>", "proposed": "<sustainable alternative>", "impact": "<environmental benefit>"}},
    "ingredients": {{"current": "<current sourcing>", "proposed": "<sustainable sourcing>", "impact": "<benefit>"}},
    "production": {{"current": "<current process>", "proposed": "<greener process>", "impact": "<benefit>"}},
    "distribution": {{"current": "<current>", "proposed": "<improved>", "impact": "<benefit>"}},
    "end_of_life": {{"current": "<current>", "proposed": "<circular economy approach>", "impact": "<benefit>"}}
  }},
  "estimated_co2_reduction": "<e.g. 45% reduction if all changes implemented>",
  "implementation_difficulty": "<Easy|Medium|Hard>",
  "summary": "<2-3 sentence blueprint summary>"
}}"""
    }

    user_prompt = focus_prompts.get(focus, focus_prompts["full"])

    async def generate():
        try:
            from fridge_observer.ai_client import k2_chat

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            full_response = await k2_chat(messages, stream=False)
            raw_answer = _extract_answer(full_response)

            # Try to parse as JSON
            try:
                # Strip any markdown code fences if present
                clean = raw_answer.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                parsed = _json.loads(clean)
                yield f"data: {_json.dumps({'type': 'structured', 'focus': focus, 'data': parsed})}\n\n"
            except (_json.JSONDecodeError, Exception):
                # Fallback: send as plain text
                yield f"data: {_json.dumps({'type': 'text', 'focus': focus, 'data': raw_answer})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as exc:
            logger.error("K2 product analysis error: %s", exc)
            yield f"data: {_json.dumps({'type': 'error', 'data': 'Unable to analyse this product right now.'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/blueprint-image")
async def get_blueprint_image(product: str):
    """
    Generate a product blueprint image using Gemini image generation.
    API key slot — returns placeholder when key not configured.
    """
    import os
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    if not gemini_key:
        # Return a placeholder SVG blueprint
        svg = _generate_placeholder_svg(product)
        from fastapi.responses import Response
        return Response(content=svg, media_type="image/svg+xml")

    # TODO: Implement Gemini image generation when API key is available
    # The Banana Pi BPI-M2 Zero (Nano Banana Pro 3) will be used as the
    # compute unit for generating product blueprint visualisations
    svg = _generate_placeholder_svg(product)
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")


def _generate_placeholder_svg(product: str) -> str:
    """Generate a clean SVG blueprint placeholder for a product."""
    safe = product[:30].replace("<", "").replace(">", "").replace("&", "and")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#c8e6d0" stroke-width="0.5"/>
    </pattern>
  </defs>
  <rect width="400" height="280" fill="#EBF3EE" rx="12"/>
  <rect width="400" height="280" fill="url(#grid)" rx="12"/>
  <rect x="40" y="40" width="320" height="160" fill="none" stroke="#4A7C59" stroke-width="2" rx="8" stroke-dasharray="8,4"/>
  <rect x="60" y="60" width="280" height="120" fill="none" stroke="#4A7C59" stroke-width="1" rx="4" opacity="0.5"/>
  <line x1="200" y1="40" x2="200" y2="200" stroke="#4A7C59" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.4"/>
  <line x1="40" y1="120" x2="360" y2="120" stroke="#4A7C59" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.4"/>
  <circle cx="200" cy="120" r="30" fill="none" stroke="#4A7C59" stroke-width="1.5" opacity="0.6"/>
  <circle cx="200" cy="120" r="5" fill="#4A7C59" opacity="0.8"/>
  <line x1="40" y1="210" x2="360" y2="210" stroke="#4A7C59" stroke-width="1" opacity="0.3"/>
  <line x1="40" y1="205" x2="40" y2="215" stroke="#4A7C59" stroke-width="1.5"/>
  <line x1="360" y1="205" x2="360" y2="215" stroke="#4A7C59" stroke-width="1.5"/>
  <text x="200" y="208" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="10" fill="#4A7C59">← 320mm →</text>
  <text x="200" y="240" text-anchor="middle" font-family="Inter, sans-serif" font-size="13" font-weight="600" fill="#2d5a3d">{safe}</text>
  <text x="200" y="258" text-anchor="middle" font-family="Inter, sans-serif" font-size="10" fill="#6B6860">Sustainability Blueprint</text>
  <text x="200" y="272" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="9" fill="#A8A59E">[ Gemini Vision — API key required ]</text>
</svg>"""
