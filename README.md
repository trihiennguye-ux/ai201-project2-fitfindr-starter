<!-- # FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design. -->

# FitFindr — README

## Overview

FitFindr is an AI agent that helps users find thrifted clothing items matching their style and budget, then suggests outfit pairings from their wardrobe and generates a shareable "fit card" caption. The agent runs a fixed 4-step pipeline (parse → search → suggest outfit → create fit card) coordinated through a central session dict, with each step's output feeding the next.

---

## Tool Inventory

### 1. `search_listings(description: str, size: str, max_price: float)`

**Purpose:** Searches the mock listings dataset for items matching the user's description, size, and budget, returning a ranked list of candidates.

**Inputs:**
- `description` (str) — free-text description of the item the user wants
- `size` (str) — desired clothing size (case-insensitive; e.g. `"M"` matches `"S/M"`)
- `max_price` (float) — upper budget limit

**Output:** A list of listing dicts, each containing `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand` (nullable), and `platform`. Results are sorted by relevance score (keyword overlap with `description`), highest first. Returns an empty list if nothing matches.

---

### 2. `suggest_outfit(new_item: dict, wardrobe: dict)`

**Purpose:** Uses an LLM (Groq) to suggest outfit combinations pairing the newly found item with pieces from the user's existing wardrobe, based on matching `style_tags` and `colors`.

**Inputs:**
- `new_item` (dict) — a listing dict from `search_listings` (uses `title`, `colors`, `style_tags`, `category`, `description`)
- `wardrobe` (dict) — the user's wardrobe, containing an `items` key with a list of wardrobe item dicts (`id`, `name`, `category`, `colors`, `style_tags`, `notes`)

**Output:** A non-empty string with 1–2 outfit suggestions (or generic styling advice if the wardrobe is empty), including concrete layering/color/occasion tips and an optional mention of the overall vibe.

---

### 3. `create_fit_card(outfit: str, new_item: dict)`

**Purpose:** Uses an LLM (Groq, high temperature) to generate a casual, shareable OOTD-style social caption for the item and outfit.

**Inputs:**
- `outfit` (str) — the outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict) — the listing dict (uses `title`, `price`, `platform`, `colors`, `style_tags`, `condition`)

**Output:** A non-empty 2–4 sentence caption mentioning the item name, price, and platform once each, written in a casual, varied tone.

---

## Planning Loop

The planning loop in `agent.py` (`run_agent`) is **linear and deterministic** — it always executes the same four tools in the same order, and only branches on the presence of data/errors, not on dynamic re-planning:

1. **Parse** the user query into `description`, `size`, and `max_price`.
2. **Search** listings using the parsed parameters. If results are empty, set `session["error"]` and halt immediately.
3. **Select** the top-ranked listing and pass it (with the wardrobe) to `suggest_outfit`.
4. **Create** a fit card caption from the outfit suggestion and selected item.
5. **Return** the completed session for the UI to display.

The loop "knows it's done" once all four steps complete without an early-exit condition (empty search results being the only thing that triggers early termination). Tool-level failures (e.g. empty wardrobe, empty outfit string) are handled *inside* each tool via fallbacks, so they never propagate up as exceptions or alter the loop's control flow.

---

## State Management

All data flows through a single **session dict** created at the start of `run_agent` and passed by reference through each step:

```python
session = {
    "query": str,
    "parsed": dict,
    "search_results": list[dict],
    "selected_item": dict | None,
    "wardrobe": dict,
    "outfit_suggestion": str | None,
    "fit_card": str | None,
    "error": str | None,
}
```

Each tool reads only the fields it needs from `session` and writes its output back into a new field — there's no hidden global state. `app.py`'s `handle_query()` is the only consumer outside the loop; it reads `session["error"]`, `session["selected_item"]`, `session["outfit_suggestion"]`, and `session["fit_card"]` to populate the three UI panels (or shows the error message if `session["error"]` is set).

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | No listings match description/size/price | `session["error"]` is set to a message suggesting the user raise their budget, drop the size filter, or try different keywords. The loop halts before calling `suggest_outfit` or `create_fit_card`. |
| `suggest_outfit` | `wardrobe["items"]` is empty | Skips wardrobe matching; calls the LLM with only the new item's `colors`, `style_tags`, and `category` to produce generic styling advice, appended with a note to add wardrobe items for personalization. Never returns an empty string. |
| `create_fit_card` | `outfit` is empty or whitespace-only | Returns a text-only fallback string (`"[title] from [platform] — $[price]. [condition]. Add to fit."`) without raising an exception, and logs which field was missing. |

**Concrete example from testing:** When testing `search_listings` with the query `"impossible item"` and `max_price=1.0`, no listings matched (everything in `data/listings.json` is priced above $1). The function correctly returned `[]`, and `run_agent` set `session["error"] = "No items found for 'impossible item' under $1.00. Try increasing your budget, removing size filters, or using different keywords."` The loop halted there — `suggest_outfit` and `create_fit_card` were never called, and `handle_query()` displayed the error message in the listing panel while leaving the outfit and fit card panels empty, exactly as specified.

---

## Spec Reflection

Writing the planning.md before implementation made the actual coding step much faster — most of the ambiguity (what happens on empty results, what happens with an empty wardrobe, what the session dict looks like) was resolved on paper rather than discovered mid-debugging. The biggest gap between the spec and reality was in `parse_query()`: natural language queries are messier than the clean examples in the spec (e.g., users mixing size and price in the same clause, or omitting price entirely), so the regex needed a few more edge cases than originally planned, particularly around defaulting `max_price` to `None` and handling phrases like "around $30" vs "under $30". Otherwise, the linear planning loop and session dict structure mapped almost directly onto the implementation with no major redesign needed.

---

## AI Usage

**Instance 1 — `search_listings()` implementation**

I gave Claude the full Tool 1 spec section from planning.md (description, input parameters, return format, and failure handling), along with the function signature/skeleton and the instruction to filter by `max_price` and `size` (case-insensitive, "M" matches "S/M"), score remaining listings by keyword overlap with `description`, and sort highest-first. Claude produced an implementation using a simple word-overlap scoring function with `set` intersection between query words and the listing's `title` + `style_tags` + `description`. I changed two things before using it: (1) Claude's original size-matching used exact string equality, so I overrode it to check substring containment (`size.upper() in listing["size"].upper()`) so `"M"` would match `"S/M"`; (2) I added a tie-breaker to sort by `price` ascending when relevance scores were equal, since the spec implied returning the most relevant *and* most affordable item first, which Claude's version didn't address.

**Instance 2 — Architecture diagram → `run_agent()`**

I gave Claude the ASCII architecture diagram from planning.md (the box showing the Planning Loop with the four steps, error branches, and session field updates) plus the Session Dict Structure code block, and asked it to implement `run_agent(query, wardrobe)` following that exact flow. Claude's first pass returned the session dict immediately after `search_listings` returned an empty list, but it forgot to set `session["selected_item"] = None` in that branch, which caused `handle_query()` to throw a `KeyError` when checking for `selected_item` on the error path. I added the explicit `session["selected_item"] = None` (and `session["outfit_suggestion"] = None`, `session["fit_card"] = None`) initialization at the top of `run_agent` before the early-return branches, so all session keys are always present regardless of where the loop halts — matching the "all fields populated" guarantee from the State Management section of planning.md.