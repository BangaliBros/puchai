import asyncio
from typing import Annotated, List, Dict, Any
import os
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

# -------------------------
# Room search input model
# -------------------------
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
    use_when="User wants to find rooms or roommates with simple filters inside WhatsApp.",
    side_effects=None,
)

# --- Tool: room_finder (search only) ---
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

    # Validate gender value if provided
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

    # Sort and limit
    results.sort(key=lambda x: (x.get("rent", 0), x.get("date_posted", "")))
    results = results[:limit]

    # Prepare output
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
        spots = r.get("spots_available")  # NEW
        spots_s = f"{spots}" if isinstance(spots, int) else "—"

        lines.append(
            "\n".join(
                [
                    f"**ID:** `{r.get('id')}`",
                    f"**Location:** {city_s} • {area_s} • {pin_s}",
                    f"**Rent:** ₹{r.get('rent')}/month",
                    f"**Gender Pref:** {r.get('gender_pref','Any')}",
                    f"**Spots Available:** {spots_s}",   # NEW
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
