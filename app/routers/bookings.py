from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
import re
from typing import Optional
from datetime import date, datetime
from app.database import get_connection

router = APIRouter(prefix="/bookings", tags=["Bookings"])


class BookingRequest(BaseModel):
    property_slug: str
    checkin_date: date
    checkout_date: date
    num_adults: int
    num_kids: int = 0
    num_infants: int = 0
    guest_name: str
    guest_email: EmailStr
    guest_phone: str
    special_requests: Optional[str] = None

    @field_validator('guest_name')
    @classmethod
    def name_must_be_letters(cls, v):
        if not re.match(r'^[a-zA-Z\s]+$', v.strip()):
            raise ValueError('Name can only contain letters')
        return v.strip().title()

    @field_validator('guest_phone')
    @classmethod
    def phone_must_be_10_digits(cls, v):
        digits = re.sub(r'\D', '', v)
        if len(digits) != 10:
            raise ValueError('Phone number must be exactly 10 digits')
        return digits


def generate_booking_ref(conn) -> str:
    cur = conn.cursor()
    today = datetime.now().strftime("%Y%m%d")
    cur.execute("SELECT COUNT(*) as cnt FROM bookings WHERE booking_ref LIKE %s", (f"BK-{today}-%",))
    count = cur.fetchone()["cnt"] + 1
    return f"BK-{today}-{str(count).zfill(4)}"


@router.post("/", status_code=201)
def create_booking(payload: BookingRequest):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, max_guests, price_per_night
            FROM properties
            WHERE slug = %s AND is_active = TRUE
        """, (payload.property_slug,))
        prop = cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        property_id = prop["id"]
        max_guests = prop["max_guests"]
        price_per_night = prop["price_per_night"]

        total_guests = payload.num_adults + payload.num_kids
        if total_guests > max_guests:
            raise HTTPException(status_code=400, detail=f"Guest count {total_guests} exceeds property maximum of {max_guests}")

        cur.execute("""
            SELECT COUNT(*) as cnt FROM inventory
            WHERE property_id = %s AND date >= %s AND date < %s AND is_available = FALSE
        """, (property_id, payload.checkin_date, payload.checkout_date))
        if cur.fetchone()["cnt"] > 0:
            raise HTTPException(status_code=409, detail="Some dates in your range are unavailable")

        cur.execute("""
            INSERT INTO guests (full_name, email, phone) VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name, phone = EXCLUDED.phone
            RETURNING id
        """, (payload.guest_name, payload.guest_email, payload.guest_phone))
        guest_id = cur.fetchone()["id"]

        booking_ref = generate_booking_ref(conn)
        cur.execute("""
            INSERT INTO bookings (
                booking_ref, property_id, guest_id,
                checkin_date, checkout_date,
                num_adults, num_kids, num_infants,
                price_per_night, status, special_requests
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed', %s)
            RETURNING id, booking_ref, total_amount
        """, (
            booking_ref, property_id, guest_id,
            payload.checkin_date, payload.checkout_date,
            payload.num_adults, payload.num_kids, payload.num_infants,
            price_per_night, payload.special_requests
        ))
        booking = cur.fetchone()

        cur.execute("""
            UPDATE inventory SET is_available = FALSE, blocked_reason = 'booked'
            WHERE property_id = %s AND date >= %s AND date < %s
        """, (property_id, payload.checkin_date, payload.checkout_date))

        conn.commit()

        nights = (payload.checkout_date - payload.checkin_date).days
        return {
            "success": True,
            "booking_ref": booking["booking_ref"],
            "booking_id": booking["id"],
            "num_nights": nights,
            "total_amount": float(booking["total_amount"]),
            "message": f"Booking confirmed! Reference: {booking['booking_ref']}"
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/")
def list_bookings():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT b.id, b.booking_ref,
                p.name AS property_name, p.location AS property_location,
                g.full_name AS guest_name, g.email AS guest_email, g.phone AS guest_phone,
                b.checkin_date, b.checkout_date, b.num_nights,
                b.num_adults, b.num_kids, b.num_infants, b.total_guests,
                b.price_per_night, b.total_amount, b.status, b.special_requests, b.created_at
            FROM bookings b
            JOIN properties p ON p.id = b.property_id
            JOIN guests g ON g.id = b.guest_id
            ORDER BY b.created_at DESC
        """)
        return cur.fetchall()
    finally:
        conn.close()
