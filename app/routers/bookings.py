from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
import re
import os
import resend
from typing import Optional
from datetime import date, datetime
from app.database import get_connection

router = APIRouter(prefix="/bookings", tags=["Bookings"])

resend.api_key = os.environ.get("RESEND_API_KEY")


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


def send_confirmation_email(
    guest_name: str,
    guest_email: str,
    booking_ref: str,
    property_name: str,
    property_location: str,
    checkin_date: date,
    checkout_date: date,
    num_nights: int,
    num_adults: int,
    num_kids: int,
    num_infants: int,
    total_amount: float,
    special_requests: Optional[str],
):
    try:
        checkin_str = checkin_date.strftime("%d %B %Y")
        checkout_str = checkout_date.strftime("%d %B %Y")
        total_str = f"₹{total_amount:,.2f}"

        guest_summary = f"{num_adults} adult{'s' if num_adults > 1 else ''}"
        if num_kids > 0:
            guest_summary += f", {num_kids} child{'ren' if num_kids > 1 else ''}"
        if num_infants > 0:
            guest_summary += f", {num_infants} infant{'s' if num_infants > 1 else ''}"

        special_row = f"""
            <tr>
                <td style="padding: 10px 0; color: #78716c; font-size: 14px;">Special Requests</td>
                <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{special_requests}</td>
            </tr>
        """ if special_requests else ""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin: 0; padding: 0; background-color: #f7f4ef; font-family: Georgia, serif;">
            <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">

                <!-- Header -->
                <div style="background-color: #1c1917; padding: 40px 40px 30px; text-align: center;">
                    <h1 style="margin: 0; color: white; font-size: 28px; letter-spacing: 1px;">
                        Aureo<span style="color: #d97706;">Stays</span>
                    </h1>
                    <p style="margin: 6px 0 0; color: #a8a29e; font-size: 11px; letter-spacing: 3px; text-transform: uppercase;">
                        Curated Villa Experiences
                    </p>
                </div>

                <!-- Confirmation Banner -->
                <div style="background-color: #d97706; padding: 24px 40px; text-align: center;">
                    <p style="margin: 0; color: white; font-size: 20px; font-weight: bold;">
                        🎉 Booking Confirmed!
                    </p>
                </div>

                <!-- Body -->
                <div style="padding: 40px;">
                    <p style="color: #1c1917; font-size: 16px; margin-top: 0;">
                        Dear {guest_name},
                    </p>
                    <p style="color: #57534e; font-size: 15px; line-height: 1.7;">
                        Your villa booking is confirmed. We're delighted to host you and look forward to making your stay exceptional.
                    </p>

                    <!-- Booking Reference -->
                    <div style="background-color: #fef3c7; border: 1px solid #fde68a; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0;">
                        <p style="margin: 0 0 6px; color: #d97706; font-size: 11px; letter-spacing: 2px; text-transform: uppercase;">
                            Booking Reference
                        </p>
                        <p style="margin: 0; color: #92400e; font-size: 28px; font-weight: bold; letter-spacing: 1px;">
                            {booking_ref}
                        </p>
                        <p style="margin: 8px 0 0; color: #a16207; font-size: 12px;">
                            Please save this reference number
                        </p>
                    </div>

                    <!-- Booking Details -->
                    <h2 style="color: #1c1917; font-size: 16px; margin-bottom: 4px;">Booking Details</h2>
                    <hr style="border: none; border-top: 1px solid #e7e5e4; margin-bottom: 16px;">

                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; color: #78716c; font-size: 14px; width: 45%;">Property</td>
                            <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{property_name}</td>
                        </tr>
                        <tr style="background-color: #fafaf9;">
                            <td style="padding: 10px 0; color: #78716c; font-size: 14px;">Location</td>
                            <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{property_location}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; color: #78716c; font-size: 14px;">Check-in</td>
                            <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{checkin_str}</td>
                        </tr>
                        <tr style="background-color: #fafaf9;">
                            <td style="padding: 10px 0; color: #78716c; font-size: 14px;">Check-out</td>
                            <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{checkout_str}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; color: #78716c; font-size: 14px;">Duration</td>
                            <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{num_nights} night{'s' if num_nights > 1 else ''}</td>
                        </tr>
                        <tr style="background-color: #fafaf9;">
                            <td style="padding: 10px 0; color: #78716c; font-size: 14px;">Guests</td>
                            <td style="padding: 10px 0; color: #1c1917; font-size: 14px; font-weight: 600;">{guest_summary}</td>
                        </tr>
                        {special_row}
                        <tr>
                            <td style="padding: 14px 0; color: #1c1917; font-size: 15px; font-weight: bold; border-top: 2px solid #e7e5e4;">Total Amount</td>
                            <td style="padding: 14px 0; color: #d97706; font-size: 18px; font-weight: bold; border-top: 2px solid #e7e5e4;">{total_str}</td>
                        </tr>
                    </table>

                    <!-- Footer note -->
                    <div style="background-color: #f7f4ef; border-radius: 10px; padding: 16px 20px; margin-top: 28px;">
                        <p style="margin: 0; color: #78716c; font-size: 13px; line-height: 1.6;">
                            📍 Our team will reach out closer to your arrival date with check-in instructions and any additional details.
                            If you have any questions, simply reply to this email.
                        </p>
                    </div>

                    <p style="color: #57534e; font-size: 15px; margin-top: 28px;">
                        Warm regards,<br>
                        <strong style="color: #1c1917;">Team AureoStays</strong>
                    </p>
                </div>

                <!-- Footer -->
                <div style="background-color: #1c1917; padding: 20px 40px; text-align: center;">
                    <p style="margin: 0; color: #78716c; font-size: 12px;">
                        © 2026 AureoStays · <a href="https://villa-frontend.vercel.app" style="color: #d97706; text-decoration: none;">villa-frontend.vercel.app</a>
                    </p>
                </div>

            </div>
        </body>
        </html>
        """

        resend.Emails.send({
            "from": "AureoStays <onboarding@resend.dev>",
            "to": [guest_email],
            "subject": f"Your booking is confirmed — {property_name} 🎉",
            "html": html,
        })

    except Exception as e:
        print(f"Email sending failed: {e}")


@router.post("/", status_code=201)
def create_booking(payload: BookingRequest):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, max_guests, price_per_night, name, location
            FROM properties
            WHERE slug = %s AND is_active = TRUE
        """, (payload.property_slug,))
        prop = cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        property_id = prop["id"]
        max_guests = prop["max_guests"]
        price_per_night = prop["price_per_night"]
        property_name = prop["name"]
        property_location = prop["location"]

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

        # Send confirmation email (non-blocking — failure won't affect booking)
        send_confirmation_email(
            guest_name=payload.guest_name,
            guest_email=str(payload.guest_email),
            booking_ref=booking["booking_ref"],
            property_name=property_name,
            property_location=property_location,
            checkin_date=payload.checkin_date,
            checkout_date=payload.checkout_date,
            num_nights=nights,
            num_adults=payload.num_adults,
            num_kids=payload.num_kids,
            num_infants=payload.num_infants,
            total_amount=float(booking["total_amount"]),
            special_requests=payload.special_requests,
        )

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