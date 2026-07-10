from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import properties, bookings

app = FastAPI(
    title="Villa Booking API",
    description="Backend for Aureo Stays villa booking platform",
    version="1.0.0"
)

# Allow frontend (any origin during dev — tighten this in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties.router)
app.include_router(bookings.router)


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "ok", "message": "Villa Booking API is running"}
