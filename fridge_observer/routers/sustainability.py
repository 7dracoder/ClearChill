from __future__ import annotations

"""Sustainability Blueprint endpoint — product analysis powered by K2-Think, image generation by Dedalus Labs."""
import logging
import json as _json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from fridge_observer.db import get_db

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
    """Extract the JSON answer from K2 response — tries multiple strategies."""
    import re

    # Strategy 1: After ---ANSWER--- separator
    if ANSWER_SEP in text:
        candidate = text.rsplit(ANSWER_SEP, 1)[1].strip()
        if '{' in candidate:
            return candidate

    # Strategy 2: Find the last complete JSON object in the text
    # K2 often writes the final JSON at the end after reasoning
    json_matches = list(re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL))
    if json_matches:
        # Return the largest JSON block (most likely the complete answer)
        return max(json_matches, key=lambda m: len(m.group(0))).group(0)

    # Strategy 3: Last paragraph
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    return paragraphs[-1] if paragraphs else text.strip()


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/inventory-items")
async def get_inventory_items():
    """Get all inventory items for EcoScan - synced with dashboard inventory."""
    from fridge_observer.supabase_client import get_supabase
    sb = get_supabase()
    # Get all items (no user filtering for local dev)
    result = sb.table("food_items").select("id, name, category").order("name").execute()
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

            # Try to parse as JSON — find the first valid JSON object
            parsed = None
            clean = raw_answer.strip()

            # Remove markdown fences
            if "```" in clean:
                for part in clean.split("```"):
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        clean = part
                        break

            # Try direct parse
            try:
                parsed = _json.loads(clean)
            except _json.JSONDecodeError:
                # Find JSON object in the text using regex
                import re
                match = re.search(r'\{[\s\S]*\}', clean)
                if match:
                    try:
                        parsed = _json.loads(match.group(0))
                    except _json.JSONDecodeError:
                        pass

            if parsed:
                yield f"data: {_json.dumps({'type': 'structured', 'focus': focus, 'data': parsed})}\n\n"
            else:
                # Fallback: send as plain text
                yield f"data: {_json.dumps({'type': 'text', 'focus': focus, 'data': raw_answer})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as exc:
            logger.error("K2 product analysis error: %s", exc)
            yield f"data: {_json.dumps({'type': 'error', 'data': 'Unable to analyse this product right now.'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/blueprint-image")
async def get_blueprint_image(
    product: str,
    spec: str = ""
):
    """
    Generate a technical blueprint image for the new sustainable product.
    Uses AI for image generation.
    Falls back to SVG rendering if image generation fails.
    """
    from fastapi.responses import Response
    from fridge_observer.image_gen import generate_blueprint_image
    
    # Try to generate blueprint image using AI
    image_bytes = await generate_blueprint_image(product, spec)
    
    if image_bytes:
        # Return the generated image
        return Response(content=image_bytes, media_type="image/png")
    
    # Fallback to SVG if image generation fails
    blueprint_data = await _generate_blueprint_specs(product, spec)
    svg = _render_blueprint_svg(product, blueprint_data)
    return Response(content=svg.encode("utf-8"), media_type="image/svg+xml")


async def _generate_blueprint_specs(product: str, existing_spec: str = "") -> dict:
    """Use K2 to generate precise material and design specs for the blueprint."""
    try:
        from fridge_observer.ai_client import k2_chat, ANSWER_SEP
        import re

        context = f"\nExisting redesign notes: {existing_spec}" if existing_spec else ""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a sustainable product designer. Generate precise technical specifications "
                    "for a new eco-friendly product. Respond ONLY with valid JSON after the separator.\n\n"
                    f"FORMAT: {ANSWER_SEP}\n{{...}}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Create a technical blueprint specification for a new sustainable version of: {product}{context}\n\n"
                    "Return JSON with exactly these fields:\n"
                    "{\n"
                    '  "product_name": "<new eco product name>",\n'
                    '  "shape": "<e.g. Cylindrical bottle, Rectangular box, Pouch>",\n'
                    '  "dimensions": "<e.g. 200mm × 80mm × 80mm>",\n'
                    '  "primary_material": "<e.g. 100% recycled PET, Bamboo composite, Glass>",\n'
                    '  "secondary_material": "<e.g. Plant-based ink label, Cork stopper>",\n'
                    '  "packaging_type": "<e.g. Refillable bottle, Compostable pouch>",\n'
                    '  "certifications": ["<e.g. FSC Certified>", "<e.g. Compostable>", "<e.g. Carbon Neutral>"],\n'
                    '  "co2_reduction": "<e.g. 65% less CO2 vs original>",\n'
                    '  "recyclability": "<e.g. 100% recyclable, Compostable in 90 days>",\n'
                    '  "key_feature": "<one standout sustainability feature>"\n'
                    "}"
                ),
            },
        ]

        response = await k2_chat(messages, stream=False)

        # Extract JSON
        if ANSWER_SEP in response:
            candidate = response.rsplit(ANSWER_SEP, 1)[1].strip()
        else:
            candidate = response

        # Clean fences
        if "```" in candidate:
            for part in candidate.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    candidate = part
                    break

        # Try parse
        try:
            return _json.loads(candidate.strip())
        except Exception:
            match = re.search(r'\{[\s\S]*\}', candidate)
            if match:
                try:
                    return _json.loads(match.group(0))
                except Exception:
                    pass

    except Exception as exc:
        logger.warning("Blueprint spec generation failed: %s", exc)

    # Fallback defaults
    return {
        "product_name": f"Eco {product}",
        "shape": "Cylindrical container",
        "dimensions": "200mm × 80mm",
        "primary_material": "100% Recycled PET",
        "secondary_material": "Plant-based ink label",
        "packaging_type": "Refillable & recyclable",
        "certifications": ["FSC Certified", "Carbon Neutral", "Compostable"],
        "co2_reduction": "60% less CO2",
        "recyclability": "100% recyclable",
        "key_feature": "Closed-loop recycling system",
    }


def _wrap(text: str, max_chars: int = 25) -> list[str]:
    """Split text into lines of max_chars for SVG tspan rendering."""
    if not text or text == "—":
        return ["—"]
    
    words = str(text).split()
    lines = []
    current = ""
    
    for word in words:
        test_line = (current + " " + word).strip() if current else word
        if len(test_line) <= max_chars:
            current = test_line
        else:
            if current:
                lines.append(current)
            # If single word is too long, truncate it
            if len(word) > max_chars:
                lines.append(word[:max_chars-3] + "...")
                current = ""
            else:
                current = word
    
    if current:
        lines.append(current)
    
    return lines if lines else ["—"]


def _svg_text_block(x: int, y: int, text: str, font_size: int, fill: str,
                    font_family: str = "Inter,sans-serif", font_weight: str = "600",
                    max_chars: int = 25, line_height: int = 18) -> tuple[str, int]:
    """Render wrapped text as SVG tspan elements. Returns (svg_str, total_height)."""
    lines = _wrap(text, max_chars)
    svg = ""
    for i, line in enumerate(lines[:2]):  # max 2 lines to keep it readable
        dy = 0 if i == 0 else line_height
        svg += f'<tspan x="{x}" dy="{dy}">{_esc_svg(line)}</tspan>'
    total_height = len(lines[:2]) * line_height
    full = f'<text x="{x}" y="{y}" font-family="{font_family}" font-size="{font_size}" font-weight="{font_weight}" fill="{fill}">{svg}</text>'
    return full, total_height


def _esc_svg(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_blueprint_svg(product: str, d: dict) -> str:
    """Render a proper technical blueprint SVG with material annotations."""

    def t(key, default="—", max_len=40):
        return _esc_svg(str(d.get(key, default))[:max_len])

    product_name = t("product_name", f"Eco {product}", 50)
    shape = t("shape", "Container", 35)
    dims = t("dimensions", "—", 30)
    mat1 = t("primary_material", "Recycled material", 40)
    mat2 = t("secondary_material", "Plant-based label", 40)
    pkg_type = t("packaging_type", "Eco packaging", 40)
    co2 = t("co2_reduction", "—", 30)
    recyclability = t("recyclability", "—", 40)
    key_feature = t("key_feature", "—", 45)
    certs = d.get("certifications", [])[:3]

    # Generate wrapped text SVG for each material field with MUCH LARGER, READABLE text
    mat1_svg, mat1_h = _svg_text_block(320, 118, str(d.get("primary_material", "Recycled material")), 14, "#F0FDF4", max_chars=22, line_height=18)
    mat2_svg, mat2_h = _svg_text_block(320, 168, str(d.get("secondary_material", "Plant-based label")), 14, "#F0FDF4", max_chars=22, line_height=18)
    pkg_svg, pkg_h = _svg_text_block(320, 218, str(d.get("packaging_type", "Eco packaging")), 14, "#F0FDF4", max_chars=22, line_height=18)
    rec_svg, rec_h = _svg_text_block(320, 268, str(d.get("recyclability", "—")), 14, "#34D399", max_chars=22, line_height=18)
    feat_svg, feat_h = _svg_text_block(320, 348, str(d.get("key_feature", "—")), 13, "#A7C4B5", max_chars=24, line_height=17)

    # Cert badges
    cert_badges = ""
    for i, cert in enumerate(certs):
        x = 30 + i * 175
        cert_text = _esc_svg(str(cert)[:22])
        cert_badges += f'''
        <rect x="{x}" y="490" width="165" height="26" rx="13" fill="#1a3d2b" stroke="#34D399" stroke-width="1"/>
        <text x="{x + 82}" y="507" text-anchor="middle" font-family="Inter,sans-serif" font-size="11" fill="#34D399" font-weight="600">{cert_text}</text>'''

    # Dimension parts
    dim_parts = dims.split("×") if "×" in dims else [dims, ""]
    dim_w = dim_parts[0].strip()
    dim_h = dim_parts[1].strip() if len(dim_parts) > 1 else ""

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="540" viewBox="0 0 600 540">
  <defs>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a3d2b" stroke-width="0.4"/>
    </pattern>
    <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
      <path d="M0,0 L0,6 L6,3 z" fill="#34D399"/>
    </marker>
    <marker id="arrL" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse">
      <path d="M0,0 L0,6 L6,3 z" fill="#34D399"/>
    </marker>
    <clipPath id="matClip"><rect x="310" y="60" width="270" height="300"/></clipPath>
  </defs>

  <!-- Background -->
  <rect width="600" height="540" fill="#0A1612"/>
  <rect width="600" height="540" fill="url(#grid)" opacity="0.6"/>

  <!-- Title bar -->
  <rect x="0" y="0" width="600" height="44" fill="#0d2218"/>
  <text x="20" y="14" font-family="JetBrains Mono,monospace" font-size="9" fill="#34D399" opacity="0.7">SUSTAINABILITY BLUEPRINT — TECHNICAL SPECIFICATION</text>
  <text x="20" y="32" font-family="Inter,sans-serif" font-size="15" font-weight="700" fill="#F0FDF4">{product_name}</text>
  <text x="580" y="28" text-anchor="end" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">REV 1.0</text>

  <!-- Left: product drawing -->
  <rect x="30" y="60" width="260" height="300" rx="4" fill="none" stroke="#1a3d2b" stroke-width="1"/>

  <!-- Product silhouette -->
  <rect x="115" y="80" width="90" height="18" rx="5" fill="none" stroke="#34D399" stroke-width="1.5" stroke-dasharray="4,2"/>
  <rect x="95" y="98" width="130" height="210" rx="8" fill="#0d2218" stroke="#34D399" stroke-width="2"/>
  <!-- Label area -->
  <rect x="100" y="148" width="120" height="90" rx="4" fill="#1a3d2b" stroke="#34D399" stroke-width="1" stroke-dasharray="3,2"/>
  <text x="160" y="188" text-anchor="middle" font-family="Inter,sans-serif" font-size="10" fill="#34D399" font-weight="600">ECO LABEL</text>
  <text x="160" y="202" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">{co2}</text>
  <text x="160" y="224" text-anchor="middle" font-family="Inter,sans-serif" font-size="16" fill="#34D399">♻</text>
  <!-- Bottom cap -->
  <rect x="95" y="308" width="130" height="10" rx="3" fill="none" stroke="#34D399" stroke-width="1.5"/>

  <!-- Dimension lines -->
  <line x1="95" y1="332" x2="225" y2="332" stroke="#34D399" stroke-width="0.8" marker-start="url(#arrL)" marker-end="url(#arr)"/>
  <text x="160" y="344" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="10" fill="#34D399">{dim_w}</text>
  <line x1="238" y1="98" x2="238" y2="308" stroke="#34D399" stroke-width="0.8" marker-start="url(#arrL)" marker-end="url(#arr)"/>
  <text x="252" y="208" font-family="JetBrains Mono,monospace" font-size="10" fill="#34D399" transform="rotate(90,252,208)">{dim_h}</text>

  <!-- Shape label -->
  <text x="160" y="365" text-anchor="middle" font-family="Inter,sans-serif" font-size="11" fill="#A7C4B5">{shape}</text>

  <!-- Right: material specs (clipped) -->
  <rect x="310" y="60" width="270" height="300" rx="4" fill="none" stroke="#1a3d2b" stroke-width="1"/>
  <rect x="310" y="60" width="270" height="22" rx="4" fill="#0d2218"/>
  <text x="320" y="75" font-family="Inter,sans-serif" font-size="10" font-weight="700" fill="#34D399">MATERIALS &amp; CONSTRUCTION</text>

  <!-- Row 1: Primary material -->
  <line x1="310" y1="96" x2="580" y2="96" stroke="#1a3d2b" stroke-width="0.8"/>
  <text x="320" y="108" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">PRIMARY MATERIAL</text>
  {mat1_svg}

  <!-- Row 2: Secondary -->
  <line x1="310" y1="150" x2="580" y2="150" stroke="#1a3d2b" stroke-width="0.8"/>
  <text x="320" y="162" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">SECONDARY / LABEL</text>
  {mat2_svg}

  <!-- Row 3: Packaging type -->
  <line x1="310" y1="200" x2="580" y2="200" stroke="#1a3d2b" stroke-width="0.8"/>
  <text x="320" y="212" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">PACKAGING TYPE</text>
  {pkg_svg}

  <!-- Row 4: Recyclability -->
  <line x1="310" y1="250" x2="580" y2="250" stroke="#1a3d2b" stroke-width="0.8"/>
  <text x="320" y="262" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">RECYCLABILITY</text>
  {rec_svg}

  <!-- Row 5: CO2 -->
  <line x1="310" y1="295" x2="580" y2="295" stroke="#1a3d2b" stroke-width="0.8"/>
  <text x="320" y="307" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">CO2 REDUCTION</text>
  <text x="320" y="325" font-family="Inter,sans-serif" font-size="16" font-weight="700" fill="#34D399">{co2}</text>

  <!-- Row 6: Key feature -->
  <line x1="310" y1="338" x2="580" y2="338" stroke="#1a3d2b" stroke-width="0.8"/>
  <text x="320" y="350" font-family="JetBrains Mono,monospace" font-size="9" fill="#5E8A73">KEY FEATURE</text>
  {feat_svg}

  <!-- Certifications -->
  <rect x="30" y="375" width="550" height="100" rx="4" fill="none" stroke="#1a3d2b" stroke-width="1"/>
  <rect x="30" y="375" width="550" height="22" rx="4" fill="#0d2218"/>
  <text x="40" y="390" font-family="Inter,sans-serif" font-size="10" font-weight="700" fill="#34D399">CERTIFICATIONS &amp; COMPLIANCE</text>
  {cert_badges}

  <!-- Footer -->
  <line x1="0" y1="525" x2="600" y2="525" stroke="#1a3d2b" stroke-width="1"/>
  <text x="20" y="537" font-family="JetBrains Mono,monospace" font-size="8" fill="#5E8A73">FRIDGE OBSERVER — ECOSCAN BLUEPRINT</text>
  <text x="580" y="537" text-anchor="end" font-family="JetBrains Mono,monospace" font-size="8" fill="#5E8A73">POWERED BY AI</text>
</svg>'''
