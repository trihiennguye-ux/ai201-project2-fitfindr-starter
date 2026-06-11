"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    all_listing = load_listings()

    filtered = all_listing
    if max_price is not None:
       filtered = [l for l in filtered if l.get("price", float("inf")) <= max_price]

    if size is not None:
        size_lower = size.lower()
        filtered = [
            l for l in filtered
            if size_lower in l.get("size", "").lower()
        ]

    description_keywords = set(description.lower().split())
    scored_listings = []

    for listing in filtered:
        searchable_text = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            " ".join(listing.get("style_tags", [])),
            listing.get("category", ""),
            listing.get("brand", "") or ""
        ]).lower()
        
        searchable_keywords = set(searchable_text.split())
        score = len(description_keywords & searchable_keywords)
        
        if score > 0:
            scored_listings.append((score, listing))

    scored_listings.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()
    
    # Check if wardrobe is empty
    wardrobe_items = wardrobe.get("items", [])
    
    if not wardrobe_items:
        # Generate generic styling advice
        prompt = f"""
You are a fashion stylist. A user is considering buying this item:

Item: {new_item.get('title', 'Item')}
Colors: {', '.join(new_item.get('colors', []))}
Style tags: {', '.join(new_item.get('style_tags', []))}
Category: {new_item.get('category', '')}
Description: {new_item.get('description', '')}

The user's wardrobe is currently empty. Suggest general styling ideas for this item. What kinds of pieces pair well with it? What vibe does it suit? How could someone style it?

Keep your response friendly, practical, and 2-3 sentences. End by inviting them to add items to their wardrobe for personalized suggestions.
"""
    else:
        wardrobe_formatted = "\n".join([
            f"- {item.get('name', 'Item')}: {item.get('colors', [])} | {item.get('style_tags', [])}"
            for item in wardrobe_items
        ])
        
        prompt = f"""
You are a fashion stylist. A user is considering buying this new item:

Item: {new_item.get('title', 'Item')}
Colors: {', '.join(new_item.get('colors', []))}
Style tags: {', '.join(new_item.get('style_tags', []))}
Category: {new_item.get('category', '')}
Description: {new_item.get('description', '')}

Their current wardrobe includes:
{wardrobe_formatted}

Suggest 1-2 complete outfit combinations that pair this new item with specific pieces from their wardrobe. Be specific about which pieces go together and why. Mention the vibe or occasion.

Keep your response 3-5 sentences and practical.
"""
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7
    )
    
    return message.choices[0].message.content.strip() # type: ignore


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    client = _get_groq_client()
    if not outfit or not outfit.strip():
        fallback = (
            f"{new_item.get('title', 'Item')} from {new_item.get('platform', 'marketplace')} "
            f"— ${new_item.get('price', 'price')}. {new_item.get('condition', 'condition').capitalize()}. "
            f"Add to fit."
        )
        return fallback
    
    prompt = f"""
Write a casual 2-4 sentence Instagram/TikTok OOTD caption for this thrifted fit. 
It should feel authentic and fun, like a real post from someone excited about their outfit.

Item being styled:
- Title: {new_item.get('title', 'Item')}
- Price: ${new_item.get('price', 'TBD')}
- Platform: {new_item.get('platform', 'thrift')}
- Condition: {new_item.get('condition', '')}

Outfit & styling advice:
{outfit}

Guidelines:
- Keep it casual and conversational
- Mention the item name, price, and platform once each (weave them in naturally)
- Capture the vibe in specific style terms
- Feel free to use emojis if it fits the tone
- Sound authentic, not like marketing copy

Write only the caption text, no additional commentary.
"""
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.9
    )
    return message.choices[0].message.content.strip() # type: ignore
