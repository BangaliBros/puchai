import asyncio
from typing import Annotated, List, Dict, Any
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import INVALID_PARAMS
from pydantic import BaseModel, Field
from rooms_database import ROOMS_DB
from cities_and_areas import CITY_SYNONYMS, AREA_SYNONYMS
import re

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

def _cleanup_basic(text: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"_", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_city(text: str | None) -> str:
    if not text:
        return ""
    t = _cleanup_basic(text)
    return CITY_SYNONYMS.get(t, t)

def normalize_area(text: str | None) -> str:
    if not text:
        return ""
    t = _cleanup_basic(text)
    return AREA_SYNONYMS.get(t, t)

def normalize_amenity(a: str) -> str:
    return _cleanup_basic(a)

# --- MCP Server Setup ---
mcp = FastMCP(
    "RoomieMatch MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    return MY_NUMBER

# --- Tool: get_help (for greeting and instructions) ---
HelpDescription = RichToolDescription(
    description="Shows a help menu with instructions and examples for the RoomieMatch agent.",
    use_when=(
        "The user wants to know what commands are available or how to use the roomie bot. "
        "Use for prompts like 'roomie instructions', 'how does this work?', 'roomie agent help', 'show examples'."
    ),
    side_effects=None,
)

@mcp.tool(description=HelpDescription.model_dump_json())
async def get_help() -> str:
    """
    Generates a welcome message listing all available commands and how to use them.
    """
    welcome_message = (
        "👋 **Welcome to the RoomieMatch Assistant!**\n\n"
        "I can help you find a room or post one for rent.\n\n"
        "**🔎 How to Search:**\n"
        "Just describe what you're looking for! Examples:\n"
        "• `Find rooms in Bengaluru`\n"
        "• `Show me places in Koramangala under ₹20000`\n\n"
        "**✍️ How to List a Room:**\n"
        "Just say you want to list a room, and I'll ask for the details! Example:\n"
        "• `I want to list a room.`\n"
        "• `Post a flat for rent.`\n\n"
        "To see this message again, ask for **'roomie instructions'**."
    )
    return welcome_message


# ##################################################################
# # --- UPDATED TOOL: ADD ROOM with SLOT FILLING ---
# ##################################################################

AddRoomDescription = RichToolDescription(
    description=(
        "Adds a new room listing to the database. If essential details like city, area, "
        "rent, gender, or spots are missing, this tool will ask the user for them."
    ),
    use_when=(
        "User expresses intent to list a property. Keywords: 'add a room', "
        "'post my flat', 'list a room for rent', 'I have a room to offer'. "
        "This tool can be called even if the user has not provided all the details yet."
    ),
    side_effects="A new entry will be added to the rooms database once all required information is collected.",
)

@mcp.tool(description=AddRoomDescription.model_dump_json())
async def add_room(
    city: Annotated[str | None, Field(description="The city where the room is located, e.g., 'Pune'.", default=None)] = None,
    area: Annotated[str | None, Field(description="The specific area or neighborhood, e.g., 'Hinjewadi'.", default=None)] = None,
    rent: Annotated[int | None, Field(description="The monthly rent in INR, e.g., 15000.", default=None)] = None,
    gender_pref: Annotated[str | None, Field(description='The preferred gender for the tenant: "Male", "Female", or "Any".', default=None)] = None,
    spots_available: Annotated[int | None, Field(description="The number of beds or spots available in this listing.", default=None)] = None,
    description: Annotated[str | None, Field(description="A short, descriptive text about the room or property.", default=None)] = None,
    pincode: Annotated[str | None, Field(description="The 6-digit pincode of the area.", default=None)] = None,
    amenities: Annotated[List[str] | None, Field(description="A list of amenities available, e.g., ['WiFi', 'AC'].", default=None)] = None,
) -> str:
    """
    Adds a new room listing. If required info is missing, it asks the user for it.
    Otherwise, it adds the room to the in-memory DB.
    """
    # --- Step 1: Check for missing required information ---
    missing_fields = []
    if not city: missing_fields.append("city")
    if not area: missing_fields.append("area")
    if not rent: missing_fields.append("rent")
    if not gender_pref: missing_fields.append("gender preference (Male, Female, or Any)")
    if not spots_available: missing_fields.append("number of spots available")
    if not description: missing_fields.append("a brief description")

    if missing_fields:
        # If there are missing fields, ask the user for them.
        missing_list = ", ".join(missing_fields)
        return f"I can help with that! To list your room, please provide the following details: **{missing_list}**."

    # --- Step 2: If all fields are present, validate and process ---
    gender_n = (gender_pref or "").strip().capitalize()
    if gender_n not in {"Male", "Female", "Any"}:
        raise McpError(ErrorData(code=INVALID_PARAMS, message='gender_pref must be "Male", "Female", or "Any"'))

    # Generate New ID
    max_id = 0
    for room in ROOMS_DB:
        if room['id'].startswith('R') and room['id'][1:].isdigit():
            max_id = max(max_id, int(room['id'][1:]))
    new_id_num = max_id + 1
    new_id = f"R{new_id_num:03d}"

    # Create New Room Record
    today = date.today()
    new_room = {
        "id": new_id,
        "location": {
            "city": city.strip(),
            "area": area.strip(),
            "pincode": (pincode or "").strip()
        },
        "rent": rent,
        "gender_pref": gender_n,
        "amenities": amenities or [],
        "description": description.strip(),
        "photo_url": None,
        "posted_by": "user_via_mcp",
        "date_posted": today.isoformat(),
        "is_active": True,
        "expires_at": (today + timedelta(days=30)).isoformat(),
        "spots_available": spots_available
    }

    ROOMS_DB.append(new_room)

    return f"✅ **Success!** Your new listing has been added with ID: `{new_id}`. It is now active and searchable for 30 days."


# ##################################################################
# # --- ROOM FINDER TOOL (No changes below this line) ---
# ##################################################################

class RoomSearchInput(BaseModel):
    city: str | None = Field(default=None, description="City name to filter (e.g., Bengaluru)")
    area: str | None = Field(default=None, description="Area/neighborhood to filter (e.g., Koramangala)")
    pincode: str | None = Field(default=None, description="Pincode to filter")
    max_rent: int | None = Field(default=None, description="Maximum rent in INR")
    gender_pref: str | None = Field(default=None, description='Preferred gender: "Male"|"Female"|"Any"')
    amenities: List[str] | None = Field(default=None, description="List of required amenities, e.g., ['WiFi','AC']")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")

RoomFinderDescription = RichToolDescription(
    description=(
        "Search available rooms/flatshares from an in-memory dataset. "
        "Filter by city/area/pincode, max_rent, gender_pref, and amenities. "
        "Handles common aliases like 'Bangalore'→'Bengaluru', 'Kormangala'→'Koramangala'."
    ),
    use_when=(
        "User wants to find a room, flat, or roommate. Use this to perform a search based on user criteria. "
        "**DO NOT** use this tool if the user is asking for help, instructions, or to post a new listing."
    ),
    side_effects=None,
)

@mcp.tool(description=RoomFinderDescription.model_dump_json())
async def room_finder(
    city: Annotated[str | None, Field(description="City filter", default=None)] = None,
    area: Annotated[str | None, Field(description="Area filter", default=None)] = None,
    pincode: Annotated[str | None, Field(description="Pincode filter", default=None)] = None,
    max_rent: Annotated[int | None, Field(description="Maximum rent (INR)", default=None)] = None,
    gender_pref: Annotated[str | None, Field(description='Preferred gender: "Male"|"Female"|"Any"', default=None)] = None,
    amenities: Annotated[List[str] | None, Field(description="Amenities required", default=None)] = None,
    limit: Annotated[int, Field(description="Max results (1-50)", ge=1, le=50, default=10)] = 10,
) -> str:
    """
    Search rooms in the in-memory ROOMS_DB using deterministic normalization
    and show the number of spots available per listing.
    """
    # Normalize inputs
    city_n = normalize_city(city) if city else ""
    area_n = normalize_area(area) if area else ""
    pincode_n = (pincode or "").strip()
    gender_n = (gender_pref or "").strip().capitalize() if gender_pref else None
    req_amenities = [normalize_amenity(a) for a in (amenities or []) if a and normalize_amenity(a)]

    if gender_n and gender_n not in {"Male", "Female", "Any"}:
        raise McpError(ErrorData(code=INVALID_PARAMS, message='gender_pref must be "Male", "Female", or "Any"'))

    # Filtering
    results: List[Dict[str, Any]] = []
    for r in ROOMS_DB:
        if not r.get("is_active", False):
            continue

        loc = r.get("location", {}) or {}
        r_city = normalize_city(loc.get("city") or "")
        r_area = normalize_area(loc.get("area") or "")
        r_pincode = (loc.get("pincode") or "")

        if city_n and city_n != r_city:
            continue
        if area_n and area_n != r_area:
            continue
        if pincode_n and pincode_n != r_pincode:
            continue

        if max_rent is not None and r.get("rent", 10**9) > max_rent:
            continue

        if gender_n:
            listing_gender = r.get("gender_pref", "Any")
            if listing_gender != "Any" and listing_gender != gender_n:
                continue

        if req_amenities:
            r_amenities = [normalize_amenity(a) for a in r.get("amenities", [])]
            if not all(a in r_amenities for a in req_amenities):
                continue

        results.append(r)

    results.sort(key=lambda x: (x.get("rent", 0), x.get("date_posted", "")))
    results = results[:limit]

    if not results:
        interpreted = []
        if city_n: interpreted.append(f"city={city_n}")
        if area_n: interpreted.append(f"area={area_n}")
        if pincode_n: interpreted.append(f"pincode={pincode_n}")
        if max_rent is not None: interpreted.append(f"max_rent=₹{max_rent}")
        if gender_n: interpreted.append(f"gender={gender_n}")
        if req_amenities: interpreted.append(f"amenities={', '.join(req_amenities)}")
        interp_line = ("Searching with: " + ", ".join(interpreted)) if interpreted else "Searching with: (no filters)"
        return (
            "🔍 **No matching rooms found.**\n"
            f"{interp_line}\n\n"
            "Try widening your filters (increase budget, remove some amenities, or search by city only)."
        )

    interpreted = []
    if city_n: interpreted.append(f"city={city_n}")
    if area_n: interpreted.append(f"area={area_n}")
    if pincode_n: interpreted.append(f"pincode={pincode_n}")
    if max_rent is not None: interpreted.append(f"max_rent=₹{max_rent}")
    if gender_n: interpreted.append(f"gender={gender_n}")
    if req_amenities: interpreted.append(f"amenities={', '.join(req_amenities)}")
    interp_line = (" • " + ", ".join(interpreted)) if interpreted else ""

    lines: List[str] = []
    lines.append(f"🏠 **Room Finder Results** (showing {len(results)} result(s)){interp_line}\n")
    for r in results:
        loc = r.get("location", {})
        city_s = loc.get("city") or "-"
        area_s = loc.get("area") or "-"
        pin_s = loc.get("pincode") or "-"
        amenities_s = ", ".join(r.get("amenities", [])).strip() or "—"
        photo_s = r.get("photo_url") or "—"
        spots = r.get("spots_available")
        spots_s = f"{spots}" if isinstance(spots, int) else "—"

        lines.append(
            "\n".join(
                [
                    f"**ID:** `{r.get('id')}`",
                    f"**Location:** {city_s} • {area_s} • {pin_s}",
                    f"**Rent:** ₹{r.get('rent')}/month",
                    f"**Gender Pref:** {r.get('gender_pref','Any')}",
                    f"**Spots Available:** {spots_s}",
                    f"**Amenities:** {amenities_s}",
                    f"**Posted:** {r.get('date_posted','—')}  •  **Expires:** {r.get('expires_at','—')}",
                    f"**Photo:** {photo_s}",
                    f"**About:** {r.get('description','')}",
                    "---",
                ]
            )
        )

    return "\n".join(lines)

# --- Run MCP Server ---
async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())