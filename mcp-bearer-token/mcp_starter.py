import asyncio
from typing import Annotated, List, Dict, Any
import os
from datetime import date, timedelta
import uuid  # Using uuid to generate unique keys
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

load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(token=token, client_id="puch-client", scopes=["*"], expires_at=None)
        return None

class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None


def _cleanup_basic(text: str) -> str:
    if not text: return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"_", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_city(text: str | None) -> str:
    if not text: return ""
    return CITY_SYNONYMS.get(_cleanup_basic(text), _cleanup_basic(text))

def normalize_area(text: str | None) -> str:
    if not text: return ""
    return AREA_SYNONYMS.get(_cleanup_basic(text), _cleanup_basic(text))

def normalize_amenity(a: str) -> str:
    return _cleanup_basic(a)

# MCP Server Setup
mcp = FastMCP("RoomieMatch MCP Server", auth=SimpleBearerAuthProvider(TOKEN))

#Tool: validate
@mcp.tool
async def validate() -> str:
    return MY_NUMBER

#Tool: get_help
HelpDescription = RichToolDescription(
    description="Shows a help menu with instructions and examples.",
    use_when="User asks for 'help', 'instructions', 'commands', or 'how does this work?'.",
    side_effects=None,
)

@mcp.tool(description=HelpDescription.model_dump_json())
async def get_help() -> str:
    """Generates a welcome message explaining the manual key system."""
    welcome_message = (
        "👋 **Welcome to the RoomieMatch Assistant!**\n\n"
        "**🔎 How to Search:**\n"
        "• `Find rooms in Bengaluru`\n"
        "• `Show me places under ₹20000`\n\n"
        "**✍️ How to List a Room:**\n"
        "When you list a room, you'll get a **secret management key**. **SAVE THIS KEY!** You need it to edit or delete your listing later.\n"
        "• `I want to list a room.`\n\n"
        "**✏️ How to Manage a Listing:**\n"
        "You must provide the Room ID and your secret key.\n"
        "• `Delete room R015 with key <your_secret_key>`\n"
        "• `Edit room R015 with key <your_secret_key>, set rent to 18000`"
    )
    return welcome_message


#Tool: Add a Room
AddRoomDescription = RichToolDescription(
    description="Adds a new room listing and returns a secret management key.",
    use_when="User wants to 'add', 'post', or 'list' a room for rent.",
    side_effects="A new room is added to the database. A unique, one-time key is generated.",
)

@mcp.tool(description=AddRoomDescription.model_dump_json())
async def add_room(
    city: Annotated[str | None, Field(description="City", default=None)] = None,
    area: Annotated[str | None, Field(description="Area/neighborhood", default=None)] = None,
    rent: Annotated[int | None, Field(description="Monthly rent in INR", default=None)] = None,
    gender_pref: Annotated[str | None, Field(description='"Male"|"Female"|"Any"', default=None)] = None,
    spots_available: Annotated[int | None, Field(description="Number of spots", default=None)] = None,
    description: Annotated[str | None, Field(description="A short description", default=None)] = None,
    pincode: Annotated[str | None, Field(description="6-digit pincode", default=None)] = None,
    amenities: Annotated[List[str] | None, Field(description="List of amenities", default=None)] = None,
) -> str:
    # Slot filling logic
    missing_fields = []
    if not city: missing_fields.append("city")
    if not area: missing_fields.append("area")
    if not rent: missing_fields.append("rent")
    if not gender_pref: missing_fields.append("gender preference")
    if not spots_available: missing_fields.append("spots available")
    if not description: missing_fields.append("a description")
    if missing_fields:
        return f"To list your room, please provide: **{', '.join(missing_fields)}**."

    # Validation
    gender_n = (gender_pref or "").strip().capitalize()
    if gender_n not in {"Male", "Female", "Any"}:
        raise McpError(ErrorData(code=INVALID_PARAMS, message='gender_pref must be "Male", "Female", or "Any"'))

    # Generate IDs and Keys
    max_id = max((int(r['id'][1:]) for r in ROOMS_DB if r['id'].startswith('R') and r['id'][1:].isdigit()), default=0)
    new_id = f"R{max_id + 1:03d}"
    management_key = str(uuid.uuid4()) # Generate a new secret key
    today = date.today()

    new_room = {
        "id": new_id,
        "management_key": management_key, # Store the secret key
        "location": {"city": city.strip(), "area": area.strip(), "pincode": (pincode or "").strip()},
        "rent": rent, "gender_pref": gender_n, "amenities": amenities or [],
        "description": description.strip(), "photo_url": None,
        "date_posted": today.isoformat(), "is_active": True,
        "expires_at": (today + timedelta(days=30)).isoformat(),
        "spots_available": spots_available
    }
    ROOMS_DB.append(new_room)

    return (
        f"✅ **Success! Your room is listed with ID: `{new_id}`**\n\n"
        f"**IMPORTANT: Save your secret management key! You will NOT see it again.**\n"
        f"Your key is: `{management_key}`"
    )

#Tool: Delete a Room
DeleteRoomDescription = RichToolDescription(
    description="Deletes a room listing using the room ID and secret management key.",
    use_when="User wants to 'delete' or 'remove' a specific room, providing its ID and key.",
    side_effects="The listing is permanently removed if the key is correct.",
)
@mcp.tool(description=DeleteRoomDescription.model_dump_json())
async def delete_room(
    room_id: Annotated[str, Field(description="The public ID of the room, e.g., 'R015'.")],
    management_key: Annotated[str, Field(description="The secret key provided when you created the listing.")]
) -> str:
    """Deletes a room if the provided management key is correct."""
    room = next((r for r in ROOMS_DB if r['id'].lower() == room_id.lower()), None)
    if not room:
        return f"❌ Error: Room with ID `{room_id}` not found."
    if room.get('management_key') != management_key:
        return f"❌ Permission Denied: The management key is incorrect for room `{room_id}`."

    ROOMS_DB.remove(room)
    return f"✅ **Success!** Room listing `{room_id}` has been deleted."

# Tool: Edit a Room
EditRoomDescription = RichToolDescription(
    description="Edits a room listing using the room ID and secret management key.",
    use_when="User wants to 'edit' or 'update' a specific room, providing its ID and key.",
    side_effects="The listing is updated if the key is correct.",
)
@mcp.tool(description=EditRoomDescription.model_dump_json())
async def edit_room(
    room_id: Annotated[str, Field(description="The public ID of the room, e.g., 'R015'.")],
    management_key: Annotated[str, Field(description="The secret key provided when you created the listing.")],
    rent: Annotated[int | None, Field(description="The new monthly rent.", default=None)] = None,
    description: Annotated[str | None, Field(description="The new description.", default=None)] = None,
    spots_available: Annotated[int | None, Field(description="The new number of spots.", default=None)] = None,
    amenities: Annotated[List[str] | None, Field(description="The new list of amenities.", default=None)] = None,
) -> str:
    """Edits a room if the provided management key is correct."""
    room = next((r for r in ROOMS_DB if r['id'].lower() == room_id.lower()), None)
    if not room:
        return f"❌ Error: Room with ID `{room_id}` not found."
    if room.get('management_key') != management_key:
        return f"❌ Permission Denied: The management key is incorrect for room `{room_id}`."

    changes = []
    if rent is not None:
        room['rent'] = rent
        changes.append(f"rent to ₹{rent}")
    if description is not None:
        room['description'] = description
        changes.append("description")
    if spots_available is not None:
        room['spots_available'] = spots_available
        changes.append(f"spots available to {spots_available}")
    if amenities is not None:
        room['amenities'] = amenities
        changes.append("amenities")
    if not changes:
        return "🤔 Nothing to update. Please specify what to change, like `set rent to 18000`."

    return f"✅ **Success!** For room `{room_id}`, updated: {', '.join(changes)}."

#Tool: room_finder
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
    city_n = normalize_city(city) if city else ""
    area_n = normalize_area(area) if area else ""
    pincode_n = (pincode or "").strip()
    gender_n = (gender_pref or "").strip().capitalize() if gender_pref else None
    req_amenities = [normalize_amenity(a) for a in (amenities or []) if a and normalize_amenity(a)]

    if gender_n and gender_n not in {"Male", "Female", "Any"}:
        raise McpError(ErrorData(code=INVALID_PARAMS, message='gender_pref must be "Male", "Female", or "Any"'))

    results: List[Dict[str, Any]] = []
    for r in ROOMS_DB:
        if not r.get("is_active", False): continue
        loc = r.get("location", {}) or {}
        r_city = normalize_city(loc.get("city") or "")
        r_area = normalize_area(loc.get("area") or "")
        r_pincode = (loc.get("pincode") or "")
        if city_n and city_n != r_city: continue
        if area_n and area_n != r_area: continue
        if pincode_n and pincode_n != r_pincode: continue
        if max_rent is not None and r.get("rent", 10**9) > max_rent: continue
        if gender_n:
            listing_gender = r.get("gender_pref", "Any")
            if listing_gender != "Any" and listing_gender != gender_n: continue
        if req_amenities:
            r_amenities = [normalize_amenity(a) for a in r.get("amenities", [])]
            if not all(a in r_amenities for a in req_amenities): continue
        results.append(r)

    results.sort(key=lambda x: (x.get("rent", 0), x.get("date_posted", "")))
    results = results[:limit]

    if not results:
        return "🔍 **No matching rooms found.** Try different filters."

    lines: List[str] = []
    lines.append(f"🏠 **Room Finder Results** (showing {len(results)} result(s))\n")
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


async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())