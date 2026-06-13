# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool will take the user input query to searching a list of product that suit the description, size, and limit price. Then return that product list with ranking by the level of relevance.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The description of item provide by user query
- `size` (str): User's clothing size
- `max_price` (float): User's maximim budget for the item

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of listing objects, each containing: id, title, description, category, style_tags, size, condition, price, colors, brand (nullable), and platform.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
The agent will notifies user about the no data for the item, then it might suggest for modify in the query, like raising the max price or size or using different description. The agent will continue asking for modify until one result found, then it will proceed the next function, suggest an outfit.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given a thrifted item and the user's wardrobe, suggests complete outfit combinations by matching style_tags and colors between the new item and existing wardrobe pieces using LLM-based style matching.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A single listing object from search_listings — uses title, colors, style_tags, category, and description
- `wardrobe` (dict): The user's wardrobe dict containing an 'items' key with a list of wardrobe item dicts (each with id, name, category, colors, style_tags, notes).

**What it returns:**
<!-- Describe the return value -->
A non-empty string containing:
- 1–2 complete outfit suggestions naming specific wardrobe pieces (if wardrobe is not empty)
- OR generic styling advice (if wardrobe is empty)
- Concrete tips for layering, color pairing, or occasions
- Optional mention of the vibe or aesthetic

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If wardrobe['items'] is empty, the LLM is called with only the item's own colors and style_tags to generate generic styling advice (e.g., "This pairs well with…", "The vibe suits…"). A note is included: "Add more items to your wardrobe for personalized outfit suggestions." Never return empty string.
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generates a short, shareable Instagram/TikTok-style outfit caption for the thrifted item, incorporating the outfit suggestion and item details using LLM-based caption generation.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion string from suggest_outfit() — describes styling ideas and wardrobe pieces
- `new_item` (dict): The listing dict for the item — uses title, price, platform, colors, style_tags, condition

**What it returns:**
<!-- Describe the return value -->
A non-empty string (2–4 sentences) formatted as a casual OOTD caption:
- Mentions the item name, price, and platform once each (naturally, not as a list)
- Feels authentic and conversational (like a real social media post)
- Captures the outfit vibe in specific style terms
- Varies in tone and phrasing for different inputs (uses LLM temperature 0.8+)

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If outfit string is empty or whitespace-only, return a text-only fallback: "[Item Title] from [Platform] — $[Price]. [Condition]. Add to fit." Do not raise an exception. Log which field was missing for debugging.
---

### Tool 4: price_comparison

**What it does:**
Analyzes whether a thrifted item's price is fair by comparing it against similar items in the dataset. Returns a price fairness assessment with reasoning and a suggested price range.

**Input parameters:**
- `item` (dict): A listing dict from search_listings — uses price, category, condition, and style_tags
- `listings` (list[dict]): The full or filtered listings dataset to compare against (optional; defaults to all listings)

**What it returns:**
A dict containing:
- `fairness_rating` (str): One of "great_deal", "fair_price", "overpriced"
- `reasoning` (str): 1–2 sentence explanation comparing to similar items
- `comparable_items_count` (int): Number of similar items used for comparison
- `price_range_low` (float): Estimated low end for this category/condition
- `price_range_high` (float): Estimated high end for this category/condition

**What happens if it fails or returns nothing:**
If no comparable items exist (e.g., single item in category), return a neutral assessment with empty `reasoning` and count = 0. Never raise an exception.

---

### Tool 5: retry_search_with_fallback

**What it does:**
Wraps search_listings with intelligent retry logic. If the initial search returns no results, automatically removes constraints (size filter, then price tolerance) and retries, informing the user what was adjusted.

**Input parameters:**
- `description` (str): The description of the item
- `size` (str | None): Desired clothing size
- `max_price` (float | None): Maximum budget
- `price_tolerance` (float): Optional buffer (e.g., 0.15 = ±15%) to relax price constraints on retry. Defaults to 0.20 (20%).

**What it returns:**
A dict containing:
- `results` (list[dict]): Matching listings (sorted by relevance)
- `adjustments_made` (list[str]): List of human-readable strings describing what was loosened (e.g., ["Removed size filter", "Increased budget to $35"])
- `original_constraints` (dict): The original {description, size, max_price} for reference
- `retry_count` (int): Number of retries performed (0 = found on first try)

**What happens if it fails or returns nothing:**
If retries exhaust all constraints and still return no results, set `results = []` and include a final adjustment like "All constraints removed—no results available." The calling agent (run_agent) treats empty results as before.

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The planning loop follows a mostly linear sequence, with intelligent retry logic on search failure. The loop always attempts to find items, retrying with loosened constraints before giving up.

**Sequence:**
1. **Parse query** — Extract description, size, max_price from user input
2. **Call retry_search_with_fallback** — Pass parsed values with auto-retry on empty results
   - First attempt uses original constraints
   - If empty: automatically remove size filter and retry
   - If still empty: relax price constraint (±20% buffer) and retry again
   - If still empty: remove all constraints and retry once more
   - Returns results + list of adjustments made (if any)
3. **Check results** — If still empty after all retries, set error and return. If results exist, continue.
4. **Select top 1** — Store the highest-ranked listing in session["selected_item"]
5. **Call price_comparison** — Optional: assess whether the top item's price is fair relative to similar listings
   - Stores fairness assessment in session["price_assessment"]
   - Does not block subsequent steps
6. **Call suggest_outfit** — Pass the top item + wardrobe, get outfit suggestion string
7. **Call create_fit_card** — Pass outfit suggestion + item, get fit card caption
8. **Return session** — All fields populated; ready for UI display

The agent halts immediately if search returns no results (even after retries) or if any tool raises an exception. Otherwise, it completes all tool calls in sequence and returns the populated session.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

The agent uses a single **session dict** as the central state store for one user interaction. All tools read from and write to this dict, ensuring data flows consistently from step to step.

### Session Dict Structure
```python
session = {
    "query": str,                    # Original user query (immutable)
    "parsed": dict,                  # Extracted {description, size, max_price}
    "search_results": list[dict],    # All matching listings from retry_search_with_fallback
    "search_adjustments": list[str], # Constraints loosened during retry (if any)
    "selected_item": dict | None,    # Top 1 result, passed to suggest_outfit
    "wardrobe": dict,                # User's wardrobe (items list)
    "price_assessment": dict | None, # Output from price_comparison (fairness rating, reasoning, price range)
    "outfit_suggestion": str | None, # Output from suggest_outfit
    "fit_card": str | None,          # Output from create_fit_card
    "error": str | None,             # Set if interaction halts early
}
```

### Data Flow Between Tools

1. **Parsing (run_agent):**
   - Input: `session["query"]` (e.g., "vintage graphic tee under $30, size M")
   - Parse description, size, max_price from query
   - Output: Populate `session["parsed"]` with extracted values

2. **Search with Retry Fallback → Session:**
   - Input: `session["parsed"]` fields (description, size, max_price)
   - Call `retry_search_with_fallback(description, size, max_price)`
   - Output: Store results in `session["search_results"]` and adjustments in `session["search_adjustments"]`
   - If empty after all retries: Set `session["error"]` and return early

3. **Price Comparison (optional, non-blocking):**
   - Input: `session["search_results"][0]` (top match)
   - Call `price_comparison(top_item, all_listings)`
   - Output: Store fairness assessment in `session["price_assessment"]`
   - If fails or has no comparables: Set to `None`; continue regardless

4. **Select Top Result → Suggest Outfit:**
   - Input: `session["search_results"][0]` (top match) + `session["wardrobe"]`
   - Store in `session["selected_item"] = search_results[0]`
   - Call `suggest_outfit(session["selected_item"], session["wardrobe"])`
   - Output: Store result in `session["outfit_suggestion"]`

5. **Create Fit Card:**
   - Input: `session["outfit_suggestion"]` + `session["selected_item"]`
   - Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`
   - Output: Store result in `session["fit_card"]`
   - Return completed session to caller

### Error Propagation
If any step sets `session["error"]`, the planning loop stops immediately and returns the session. The caller (app.py) checks for errors and displays them to the user.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| retry_search_with_fallback | No results after all retries | Set `session["error"]` to: "No items found. Tried removing size filter and increasing budget but still no matches. Try very different keywords or check back later." Then halt and return. |
| search_listings (direct call if used) | No results match the query | Set `session["error"]` to: "No items found for '[description]' under ${max_price}. Try increasing your budget, removing size filters, or using different keywords." Then halt and return. |
| price_comparison | No comparable items or calculation error | Set `session["price_assessment"] = None` and log the failure. Continue to next tool (non-blocking). |
| suggest_outfit | Wardrobe is empty | Skip wardrobe-based matching and call LLM with only the new item's style_tags, colors, and category. Return general styling advice like "This item pairs well with..." or "The vibe is..." Include a prompt: "Add more items to your wardrobe in the app for personalized outfit suggestions." |
| create_fit_card | Outfit input is missing or whitespace-only | Return a text-only fallback string with just the listing title, price, platform, and condition. Log which field was missing. Do not raise an exception. |

---

## Architecture

The agent architecture is organized into three layers: **Interface** (user-facing), **Planning Loop** (orchestration), and **Tools** (execution). State flows through a central session dict.

User query
    │
    ▼
app.py — handle_query()
    │
    ▼
agent.py — run_agent()
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Planning Loop                                               │
│                                                             │
│  Step 1 — Parse input                                       │
│      Extract: description, size, max_price, wardrobe        │
│          │                                                  │
│          ├── max_price missing? ──► set session["error"]    │
│          │                         return early             │
│          │                                                  │
│          ▼                                                  │
│      session: query_params, wardrobe_context saved          │
│          │                                                  │
│  Step 2 — search_listings(description, size, max_price)     │
│          │                                                  │
│          ▼                                                  │
│      results = [...]                                        │
│          │                                                  │
│          ├── results == [] ──► set session["error"]         │
│          │                    return early                  │
│          │                                                  │
│          ▼                                                  │
│      session: listings_results = results                    │
│      session: selected_item = results[0]                    │
│          │                                                  │
│  Step 3 — suggest_outfit(selected_item, wardrobe)           │
│          │                                                  │
│          ├── wardrobe.items == [] ──► generic tips fallback │
│          │                           (never blocks step 4)  │
│          │                                                  │
│          ▼                                                  │
│      session: outfit_data = { outfit_pieces,                │
│                               styling_tips, vibe }          │
│          │                                                  │
│  Step 4 — create_fit_card(new_item, outfit_data)            │
│          │                                                  │
│          ├── outfit missing fields ──► text-only fallback   │
│          │                            log missing field     │
│          │                                                  │
│          ▼                                                  │
│      session: fit_card saved                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Return session → app.py
    │
    ▼
UI display
    listing panel · outfit panel · fit card panel
    │
    ▼
User


### Component Responsibilities

- **app.py (handle_query)**: Receives user input, selects wardrobe, calls run_agent, formats output for UI
- **agent.py (run_agent)**: Initializes session, parses query, orchestrates tool calls, handles errors
- **tools.py (search_listings, suggest_outfit, create_fit_card)**: Individual tool implementations
- **Session dict**: Central state store, passed through entire flow
- **data_loader.py**: Loads mock listings and wardrobe data

---

---

## AI Tool Plan

### Milestone 3: Individual Tool Implementations

#### Tool 1: search_listings()
**AI Tool:** Claude

**Input to Claude:**
- Tool 1 spec from this planning.md (What it does, Input parameters, What it returns, Failure handling)
- Code snippet: Function signature + skeleton
- Instructions: "Use load_listings() to get all listings. Filter by max_price and size (case-insensitive, e.g., 'M' matches 'S/M'). Score remaining listings by keyword overlap with description. Sort by score, highest first. Return empty list if no matches."

**Expected output:** Implementation of search_listings() with keyword scoring logic

**Verification (before moving on):**
- Test 1: Query "vintage jeans" with max_price=50 → Should return Levi's 501 (lst_001) as top result
- Test 2: Query "graphic tee", max_price=20 → Should return Y2K Baby Tee (lst_002) as top result
- Test 3: Query "boots", size="M", max_price=100 → Should return combat boots if they match
- Run all 3 tests; if all pass and results are ranked by relevance, proceed to Tool 2

---

#### Tool 2: suggest_outfit()
**AI Tool:** Claude

**Input to Claude:**
- Tool 2 spec from this planning.md
- Sample data: 1 listing dict + 1 example wardrobe dict (from wardrobe_schema.json)
- Instructions: "Use the Groq LLM. If wardrobe is empty, call LLM with prompt: 'Suggest general styling ideas for this item: [colors, style_tags, category].' If wardrobe is not empty, call LLM with prompt: 'Suggest 1–2 complete outfits pairing this new item [title, colors, style_tags] with pieces from this wardrobe: [wardrobe items].' Return the LLM response as a string."

**Expected output:** Implementation using `_get_groq_client()` to call LLM

**Verification (before moving on):**
- Test 1 (empty wardrobe): Call with Y2K Baby Tee + empty wardrobe → Should return generic advice like "Pair with vintage jeans..." (no exception)
- Test 2 (full wardrobe): Call with Y2K Baby Tee + example wardrobe → Should suggest specific pieces like "baggy jeans" or "chunky sneakers"
- Both tests should return non-empty strings; proceed to Tool 3

---

#### Tool 3: create_fit_card()
**AI Tool:** Claude

**Input to Claude:**
- Tool 3 spec from this planning.md
- Sample data: 1 listing dict + 1 outfit string (from suggest_outfit output)
- Instructions: "Use the Groq LLM with higher temperature (0.8–1.0) for varied captions. Prompt: 'Write a 2–4 sentence Instagram/TikTok OOTD caption for this thrifted fit. Mention the item name, price, and platform once. Feel casual and authentic. Item: [title, price, platform]. Outfit: [outfit suggestion].' Handle empty outfit string by returning a fallback: 'Fallback: [title] from [platform] — $[price]. [condition]. Add this to your fit.' Do not raise an exception."

**Expected output:** Implementation using Groq with caption generation

**Verification (before moving on):**
- Test 1 (normal): Call with Y2K Baby Tee + outfit suggestion → Should return 2–4 sentence caption mentioning tee, price, Depop
- Test 2 (empty outfit): Call with Levi's jeans + empty string → Should return fallback text with title/price/platform
- Both tests should return non-empty strings; proceed to Milestone 4

---

### Milestone 4: Planning Loop & Integration

#### parse_query() (agent.py)
**AI Tool:** Claude

**Input to Claude:**
- Example queries: "vintage graphic tee under $30, size M", "black boots", "$50 white sneakers"
- Instructions: "Write a parse_query(query: str) function that extracts description, size, and max_price from natural language. Use regex or string matching. Ignore missing fields. Return dict: {description, size (or None), max_price (or None)}."

**Verification:**
- Test: "vintage tee under $30, size M" → {description: "vintage tee", size: "M", max_price: 30.0}

---

#### run_agent() (agent.py)
**AI Tool:** Claude

**Input to Claude:**
- The planning loop description from this planning.md
- Session dict structure from State Management section
- Instructions: "Implement run_agent(query, wardrobe). Create session dict. Call parse_query(). Call search_listings() with parsed values. Check for empty results and set error if needed. Select top item and call suggest_outfit(). Call create_fit_card(). Return completed session."

**Verification:**
- Integration test 1: Query "vintage graphic tee under $30" with example wardrobe → Should return session with all fields populated
- Integration test 2: Query "impossible item $1000" → Should return session with error message

---

#### handle_query() (app.py)
**AI Tool:** Claude

**Input to Claude:**
- app.py skeleton with TODO comments
- Instructions: "Complete handle_query(). Guard empty query. Select wardrobe based on choice. Call run_agent(). Check session['error']. Format session['selected_item'] as readable listing_text. Return (listing_text, session['outfit_suggestion'], session['fit_card']). Return (error_message, '', '') if error."

**Verification:**
- End-to-end test 1: Type "vintage jeans under $50" → See listing info, outfit, fit card in all 3 UI panels
- End-to-end test 2: Try empty query → See error message in first panel
- End-to-end test 3: Use empty wardrobe → Still get outfit suggestion (generic advice)

---

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Wardrobe choice:** Example wardrobe (10 items with baggy jeans, chunky sneakers, etc.)

---

### Step 1: Query Parsing

**What happens:** `run_agent()` receives the query and calls `parse_query()`.

**Function call:**
```python
parsed = parse_query("I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers.")
# Returns: {"description": "vintage graphic tee", "size": None, "max_price": 30.0}
```

**State after:** 
```python
session["parsed"] = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}
```

---

### Step 2: Search for Listings

**What happens:** `run_agent()` calls `search_listings()` with parsed parameters.

**Function call:**
```python
search_results = search_listings(
    description="vintage graphic tee",
    size=None,
    max_price=30.0
)
# Returns: [
#   {"id": "lst_002", "title": "Y2K Baby Tee — Butterfly Print", 
#    "price": 18.0, "platform": "depop", "colors": ["white", "pink", "purple"],
#    "style_tags": ["y2k", "vintage", "graphic tee", "cottagecore"], ...},
#   {"id": "lst_XXX", "title": "Vintage Graphic Tee — Nirvana", 
#    "price": 22.0, "platform": "thredUp", ...},
#   ...
# ]
```

**State after:**
```python
session["search_results"] = [lst_002, lst_XXX, ...]  # 3+ results, sorted by relevance
session["selected_item"] = session["search_results"][0]  # Y2K Baby Tee (top match)
```

If `search_results` were empty, the agent would set `session["error"]` and return early.

---

### Step 3: Generate Outfit Suggestion

**What happens:** `run_agent()` calls `suggest_outfit()` with the selected item and user's wardrobe.

**Function call:**
```python
outfit_suggestion = suggest_outfit(
    new_item=session["selected_item"],  # Y2K Baby Tee dict
    wardrobe=session["wardrobe"]        # 10-item example wardrobe
)
# Returns a string like:
# "This cute baby tee pairs perfectly with your baggy dark-wash jeans for a 
#  relaxed Y2K vibe. Layer with your oversized grey sweatshirt for a cozy look, 
#  or style it solo with your chunky white sneakers for a fun, casual fit. 
#  The pink and purple tones complement your earth-toned accessories too!"
```

**State after:**
```python
session["outfit_suggestion"] = "This cute baby tee pairs perfectly..."
```

---

### Step 4: Create Fit Card

**What happens:** `run_agent()` calls `create_fit_card()` to generate a shareable caption.

**Function call:**
```python
fit_card = create_fit_card(
    outfit=session["outfit_suggestion"],
    new_item=session["selected_item"]
)
# Returns a string like:
# "found this adorable Y2K baby tee on depop for $18 and i'm obessed 💕 
#  the butterfly print goes hard with my baggy jeans + chunky sneakers. 
#  vintage graphic tees >>> modern fast fashion. who else is obsessed with y2k vibes?"
```

**State after:**
```python
session["fit_card"] = "found this adorable Y2K baby tee..."
```

Session is now complete with all fields populated. Return to `app.py`.

---

### Final Output to User

**What happens:** `handle_query()` extracts the three strings from session and displays them in the Gradio UI.

**Listing Panel (left):**
```
Y2K Baby Tee — Butterfly Print

Condition: Excellent | Price: $18.00
Platform: Depop | Size: S/M
Colors: white, pink, purple
Category: Tops
Style Tags: y2k, vintage, graphic tee, cottagecore

Description: Super cute early 2000s baby tee with butterfly graphic. Fitted crop length. Tag says medium but fits like a small.
```

**Outfit Suggestion Panel (middle):**
```
This cute baby tee pairs perfectly with your baggy dark-wash jeans for a relaxed Y2K vibe. Layer with your oversized grey sweatshirt for a cozy look, or style it solo with your chunky white sneakers for a fun, casual fit. The pink and purple tones complement your earth-toned accessories too!
```

**Fit Card Panel (right):**
```
found this adorable Y2K baby tee on depop for $18 and i'm obessed 💕 the butterfly print goes hard with my baggy jeans + chunky sneakers. vintage graphic tees >>> modern fast fashion. who else is obsessed with y2k vibes?
```

**User sees:** All three panels populated with relevant, personalized advice. Ready to decide whether to buy the tee and how to style it.
