import asyncio
from typing import Annotated, List, Dict, Any
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, ImageContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field
from rooms_database import ROOMS_DB

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
        "Filter by city/area/pincode, max_rent, gender_pref, and amenities."
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
    Search rooms in the in-memory ROOMS_DB using simple filters.
    Returns a markdown list of matching listings.
    """
    # Normalize inputs
    city_n = (city or "").strip().lower()
    area_n = (area or "").strip().lower()
    pincode_n = (pincode or "").strip()
    gender_n = (gender_pref or "").strip().capitalize() if gender_pref else None
    req_amenities = [a.strip() for a in (amenities or []) if a.strip()]

    # Validate gender value if provided
    if gender_n and gender_n not in {"Male", "Female", "Any"}:
        raise McpError(ErrorData(code=INVALID_PARAMS, message='gender_pref must be "Male", "Female", or "Any"'))

    # Filtering
    results: List[Dict[str, Any]] = []
    for r in ROOMS_DB:
        if not r.get("is_active", False):
            continue

        loc = r.get("location", {}) or {}
        r_city = (loc.get("city") or "").lower()
        r_area = (loc.get("area") or "").lower()
        r_pincode = (loc.get("pincode") or "")

        # City/Area/Pincode match (if provided)
        if city_n and city_n not in r_city:
            continue
        if area_n and area_n not in r_area:
            continue
        if pincode_n and pincode_n != r_pincode:
            continue

        # Rent
        if max_rent is not None and r.get("rent", 10**9) > max_rent:
            continue

        # Gender preference (listing says "Female" -> only match Female seekers; "Any" matches all)
        if gender_n:
            listing_gender = r.get("gender_pref", "Any")
            if listing_gender != "Any" and listing_gender != gender_n:
                continue

        # Amenities: require all requested amenities to be present
        if req_amenities:
            r_amenities = [a.strip().lower() for a in r.get("amenities", [])]
            if not all(a.lower() in r_amenities for a in req_amenities):
                continue

        results.append(r)

    # Sort by rent ascending, then most recent date_posted
    results.sort(key=lambda x: (x.get("rent", 0), x.get("date_posted", "")))

    # Limit results
    results = results[:limit]

    # Prepare markdown output
    if not results:
        return "🔍 **No matching rooms found.** Try widening your filters (increase budget, remove some amenities, or search by city only)."

    lines: List[str] = []
    lines.append(f"🏠 **Room Finder Results** (showing {len(results)} result(s))\n")
    for r in results:
        loc = r.get("location", {})
        city_s = loc.get("city") or "-"
        area_s = loc.get("area") or "-"
        pin_s = loc.get("pincode") or "-"
        amenities_s = ", ".join(r.get("amenities", [])) or "—"
        photo_s = r.get("photo_url") or "—"
        lines.append(
            "\n".join(
                [
                    f"**ID:** `{r.get('id')}`",
                    f"**Location:** {city_s} • {area_s} • {pin_s}",
                    f"**Rent:** ₹{r.get('rent')}/month",
                    f"**Gender Pref:** {r.get('gender_pref','Any')}",
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
