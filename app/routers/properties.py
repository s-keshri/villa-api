from fastapi import APIRouter, HTTPException
from app.database import get_connection

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.get("/")
def list_properties():
    """Return all active properties for the listing page."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, slug, location, description,
                   bedrooms, beds, bathrooms, max_guests,
                   price_per_night, is_pet_friendly, amenities, photos
            FROM properties
            WHERE is_active = TRUE
            ORDER BY id
        """)
        return cur.fetchall()
    finally:
        conn.close()


@router.get("/{slug}")
def get_property(slug: str):
    """Return full details of a single property by slug."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, slug, location, description,
                   bedrooms, beds, bathrooms, max_guests,
                   price_per_night, is_pet_friendly, amenities, photos
            FROM properties
            WHERE slug = %s AND is_active = TRUE
        """, (slug,))
        prop = cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        return prop
    finally:
        conn.close()


@router.get("/{slug}/availability")
def get_availability(slug: str, checkin: str, checkout: str):
    """
    Check if a property is available for the given date range.
    checkin / checkout format: YYYY-MM-DD
    Returns available=True/False plus list of blocked dates in range.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Get property id from slug
        cur.execute("SELECT id FROM properties WHERE slug = %s", (slug,))
        prop = cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        property_id = prop["id"]

        # Find any unavailable dates in range
        cur.execute("""
            SELECT date
            FROM inventory
            WHERE property_id = %s
              AND date >= %s::date
              AND date < %s::date
              AND is_available = FALSE
            ORDER BY date
        """, (property_id, checkin, checkout))

        blocked = cur.fetchall()
        blocked_dates = [str(row["date"]) for row in blocked]

        return {
            "property_id": property_id,
            "checkin": checkin,
            "checkout": checkout,
            "available": len(blocked_dates) == 0,
            "blocked_dates": blocked_dates
        }
    finally:
        conn.close()
