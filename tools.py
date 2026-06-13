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


# ── Tool 4: price_comparison ──────────────────────────────────────────────────

def price_comparison(item: dict, listings: list[dict] | None = None) -> dict:
    """
    Estimate whether a thrifted item's price is fair by comparing against
    similar items (same category and condition) in the dataset.

    Args:
        item:     A listing dict with keys: price, category, condition, style_tags
        listings: Optional dataset to search for comparables. If None, loads all listings.

    Returns:
        A dict with:
        - fairness_rating (str): one of "great_deal", "fair_price", or "overpriced"
        - reasoning (str): 1–2 sentence explanation (empty if no comparables)
        - comparable_items_count (int): number of similar items used for comparison
        - price_range_low (float): estimated low price for similar items
        - price_range_high (float): estimated high price for similar items

    If no comparable items exist, returns neutral assessment with empty reasoning.
    Never raises an exception.
    """
    try:
        if listings is None:
            listings = load_listings()
        
        item_price = item.get("price", 0)
        item_category = item.get("category", "").lower()
        item_condition = item.get("condition", "").lower()
        
        # Find comparable items: same category and condition
        comparable = [
            l for l in listings
            if l.get("category", "").lower() == item_category
            and l.get("condition", "").lower() == item_condition
        ]
        
        if not comparable:
            return {
                "fairness_rating": "fair_price",
                "reasoning": "",
                "comparable_items_count": 0,
                "price_range_low": 0.0,
                "price_range_high": 0.0,
            }
        
        # Calculate price distribution
        prices = sorted([l.get("price", 0) for l in comparable])
        count = len(prices)
        
        # Calculate quartiles
        q1_idx = count // 4
        q3_idx = (3 * count) // 4
        
        price_range_low = prices[0]
        price_range_high = prices[-1]
        q1 = prices[q1_idx] if q1_idx < count else prices[0]
        q3 = prices[q3_idx] if q3_idx < count else prices[-1]
        median = prices[count // 2] if count > 0 else 0
        
        # Determine fairness rating based on quartiles
        if item_price <= q1:
            fairness_rating = "great_deal"
        elif item_price <= q3:
            fairness_rating = "fair_price"
        else:
            fairness_rating = "overpriced"
        
        # Generate reasoning
        if fairness_rating == "great_deal":
            reasoning = (
                f"Great deal! Similar {item_category} items in {item_condition} condition "
                f"typically sell for ${q1:.2f}–${q3:.2f}, and this is priced at ${item_price:.2f}."
            )
        elif fairness_rating == "fair_price":
            reasoning = (
                f"Fair price. Similar {item_category} items in {item_condition} condition "
                f"range from ${price_range_low:.2f} to ${price_range_high:.2f}, "
                f"with this one at ${item_price:.2f}."
            )
        else:
            reasoning = (
                f"On the higher end. Similar {item_category} items in {item_condition} condition "
                f"typically sell for ${q1:.2f}–${q3:.2f}, and this is priced at ${item_price:.2f}."
            )
        
        return {
            "fairness_rating": fairness_rating,
            "reasoning": reasoning,
            "comparable_items_count": count,
            "price_range_low": price_range_low,
            "price_range_high": price_range_high,
        }
    except Exception as e:
        print(f"[price_comparison] Error: {str(e)}")
        return {
            "fairness_rating": "fair_price",
            "reasoning": "",
            "comparable_items_count": 0,
            "price_range_low": 0.0,
            "price_range_high": 0.0,
        }


# ── Tool 5: retry_search_with_fallback ────────────────────────────────────────

def retry_search_with_fallback(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
    price_tolerance: float = 0.20,
) -> dict:
    """
    Wraps search_listings with intelligent retry logic. If the initial search
    returns no results, automatically loosens constraints and retries:
    1. Remove size filter, retry
    2. Increase max_price by price_tolerance %, retry
    3. Remove all constraints, retry once more

    Args:
        description (str): Item description
        size (str | None): Desired size, or None to skip filtering
        max_price (float | None): Max budget, or None to skip filtering
        price_tolerance (float): Buffer for price relaxation (default 0.20 = 20%)

    Returns:
        A dict with:
        - results (list[dict]): Matching listings (sorted by relevance), may be empty
        - adjustments_made (list[str]): Human-readable descriptions of loosened constraints
        - original_constraints (dict): The original {description, size, max_price}
        - retry_count (int): Number of retries performed (0 = found on first try)

    Never raises an exception.
    """
    adjustments_made = []
    retry_count = 0
    
    original_constraints = {
        "description": description,
        "size": size,
        "max_price": max_price,
    }
    
    # Attempt 1: Original constraints
    results = search_listings(description, size, max_price)
    if results:
        return {
            "results": results,
            "adjustments_made": adjustments_made,
            "original_constraints": original_constraints,
            "retry_count": retry_count,
        }
    
    # Attempt 2: Remove size filter
    if size is not None:
        retry_count += 1
        results = search_listings(description, None, max_price)
        adjustments_made.append("Removed size filter")
        if results:
            return {
                "results": results,
                "adjustments_made": adjustments_made,
                "original_constraints": original_constraints,
                "retry_count": retry_count,
            }
    
    # Attempt 3: Increase budget by price_tolerance %
    if max_price is not None:
        retry_count += 1
        relaxed_price = max_price * (1 + price_tolerance)
        results = search_listings(description, None, relaxed_price)
        adjustments_made.append(f"Increased budget to ${relaxed_price:.2f}")
        if results:
            return {
                "results": results,
                "adjustments_made": adjustments_made,
                "original_constraints": original_constraints,
                "retry_count": retry_count,
            }
    
    # Attempt 4: Remove all constraints
    retry_count += 1
    results = search_listings(description, None, None)
    adjustments_made.append("Removed all constraints")
    
    return {
        "results": results,
        "adjustments_made": adjustments_made,
        "original_constraints": original_constraints,
        "retry_count": retry_count,
    }
