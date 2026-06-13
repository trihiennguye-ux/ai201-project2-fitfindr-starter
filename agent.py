"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card, price_comparison, retry_search_with_fallback
import re


# ── query parsing ──────────────────────────────────────────────────────────────

def parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.
    
    Uses regex patterns to find:
    - Price: "under $30" or "$50" or "< $40" etc.
    - Size: "size M" or "size S/M" or "small" etc.
    - Description: everything else
    
    Returns dict with keys: description, size (or None), max_price (or None)
    """
    parsed = {
        "description": query,
        "size": None,
        "max_price": None,
    }
    
    # Extract price (look for dollar amounts with optional "under", "$", "less than")
    price_patterns = [
        r'under\s*\$?\s*(\d+(?:\.\d{2})?)',
        r'\$\s*(\d+(?:\.\d{2})?)',
        r'less than\s*\$?\s*(\d+(?:\.\d{2})?)',
        r'budget\s*\$?\s*(\d+(?:\.\d{2})?)',
    ]
    for pattern in price_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            parsed["max_price"] = float(match.group(1))
            break
    
    # Extract size (look for size specifications)
    size_patterns = [
        r'size\s+([XSMLXWXL0-9/-]+)',
        r'\b([XSMLXWXL0-9/-]+)\s+(?:fit|fits)',
    ]
    for pattern in size_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            parsed["size"] = match.group(1).strip()
            break
    
    # Extract description (remove price and size info)
    description = query
    # Remove price mentions
    description = re.sub(r'under\s*\$?\s*\d+(?:\.\d{2})?', '', description, flags=re.IGNORECASE)
    description = re.sub(r'\$\s*\d+(?:\.\d{2})?', '', description, flags=re.IGNORECASE)
    description = re.sub(r'less than\s*\$?\s*\d+(?:\.\d{2})?', '', description, flags=re.IGNORECASE)
    description = re.sub(r'budget\s*\$?\s*\d+(?:\.\d{2})?', '', description, flags=re.IGNORECASE)
    
    # Remove size mentions
    description = re.sub(r'size\s+[XSMLXWXL0-9/-]+', '', description, flags=re.IGNORECASE)
    description = re.sub(r'[XSMLXWXL0-9/-]+\s+(?:fit|fits)', '', description, flags=re.IGNORECASE)
    
    # Clean up whitespace
    description = ' '.join(description.split()).strip()
    parsed["description"] = description if description else "item"
    
    return parsed


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "search_adjustments": [],    # list of constraints loosened during retry
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "price_assessment": None,    # dict from price_comparison (optional)
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call retry_search_with_fallback() with the parsed parameters.
                Store results in session["search_results"] and adjustments in
                session["search_adjustments"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5 (optional): Call price_comparison() with the selected item.
                Store the result in session["price_assessment"].
                If this fails, continue anyway (non-blocking).

        Step 6: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 7: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 8: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    session["parsed"] = parse_query(query)

    # Use retry_search_with_fallback instead of direct search_listings call
    search_result = retry_search_with_fallback(
        description=session["parsed"].get("description", ""),
        size=session["parsed"].get("size"),
        max_price=session["parsed"].get("max_price"),
    )
    
    session["search_results"] = search_result["results"]
    session["search_adjustments"] = search_result["adjustments_made"]

    if not session["search_results"]:
        description = session["parsed"].get("description", "item")
        adjustments_text = ""
        if session["search_adjustments"]:
            # Format adjustments with proper grammar
            adjustments_list = [adj.lower() for adj in session["search_adjustments"]]
            if len(adjustments_list) == 1:
                adjustments_text = f" Tried {adjustments_list[0]} but still no matches."
            else:
                adjustments_text = (
                    f" Tried {', '.join(adjustments_list[:-1])} and {adjustments_list[-1]} but still no matches."
                )
        session["error"] = (
            f"No items found for '{description}'.{adjustments_text} "
            f"Try very different keywords (e.g., 'hoodie' instead of 'sweater') "
            f"or check back later."
        )
        return session
    
    session["selected_item"] = session["search_results"][0]
    
    # Call price_comparison (optional, non-blocking)
    try:
        session["price_assessment"] = price_comparison(session["selected_item"])
    except Exception as e:
        print(f"[run_agent] Price comparison failed: {str(e)}")
        session["price_assessment"] = None

    try:
        session["outfit_suggestion"] = suggest_outfit(
            new_item=session["selected_item"],
            wardrobe=session["wardrobe"],
        )
    except Exception as e:
        session["error"] = f"Error generating outfit suggestion: {str(e)}"
        return session
    
    try:
        session["fit_card"] = create_fit_card(
            outfit=session["outfit_suggestion"],
            new_item=session["selected_item"],
        )
    except Exception as e:
        session["error"] = f"Error generating fit card: {str(e)}"
        session["fit_card"] = None  # ensure fit_card is None if there's an error
        return session

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
