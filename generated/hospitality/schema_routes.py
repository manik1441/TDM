from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from models import Hotel, Room, Guest, Reservation, Service, ReservationService
from datetime import date

router = APIRouter(prefix="/api/tdm")

# Helper validation functions
def validate_hotel_rating(rating: int):
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Hotel rating must be between 1 and 5")

def validate_service_charge(charge: float):
    if charge < 0:
        raise HTTPException(status_code=400, detail="Service charge must be non‑negative")

def validate_dates(check_in: date, check_out: date):
    if check_in > check_out:
        raise HTTPException(status_code=400, detail="Check‑in date cannot be after check‑out date")

def validate_room_capacity(room: Room, guest_count: int):
    if room.capacity < guest_count:
        raise HTTPException(status_code=400, detail="Room capacity is less than number of guests")

# Hotels
@router.get("/hotels")
def list_hotels(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.query(Hotel).limit(limit).all()

@router.post("/hotels")
def create_hotel(payload: dict = Body(...), db: Session = Depends(get_db)):
    name = payload.get('name')
    address = payload.get('address')
    rating = payload.get('rating')
    if name is None or address is None or rating is None:
        raise HTTPException(status_code=400, detail="Missing required hotel fields")
    validate_hotel_rating(rating)
    hotel = Hotel(name=name, address=address, rating=rating)
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel

# Rooms
@router.get("/rooms")
def list_rooms(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.query(Room).limit(limit).all()

@router.post("/rooms")
def create_room(payload: dict = Body(...), db: Session = Depends(get_db)):
    number = payload.get('number')
    capacity = payload.get('capacity')
    price_per_night = payload.get('price_per_night')
    hotel_id = payload.get('hotel_id')
    if None in (number, capacity, price_per_night, hotel_id):
        raise HTTPException(status_code=400, detail="Missing required room fields")
    room = Room(number=number, capacity=capacity, price_per_night=price_per_night, hotel_id=hotel_id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room

# Guests
@router.get("/guests")
def list_guests(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.query(Guest).limit(limit).all()

@router.post("/guests")
def create_guest(payload: dict = Body(...), db: Session = Depends(get_db)):
    first_name = payload.get('first_name')
    last_name = payload.get('last_name')
    email = payload.get('email')
    phone = payload.get('phone')
    if None in (first_name, last_name, email):
        raise HTTPException(status_code=400, detail="Missing required guest fields")
    guest = Guest(first_name=first_name, last_name=last_name, email=email, phone=phone)
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest

# Services
@router.get("/services")
def list_services(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.query(Service).limit(limit).all()

@router.post("/services")
def create_service(payload: dict = Body(...), db: Session = Depends(get_db)):
    name = payload.get('name')
    description = payload.get('description')
    charge = payload.get('charge')
    hotel_id = payload.get('hotel_id')
    if None in (name, charge, hotel_id):
        raise HTTPException(status_code=400, detail="Missing required service fields")
    validate_service_charge(charge)
    service = Service(name=name, description=description, charge=charge, hotel_id=hotel_id)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service

# Reservations
@router.get("/reservations")
def list_reservations(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.query(Reservation).limit(limit).all()

@router.post("/reservations")
def create_reservation(payload: dict = Body(...), db: Session = Depends(get_db)):
    check_in = payload.get('check_in')
    check_out = payload.get('check_out')
    guest_id = payload.get('guest_id')
    room_id = payload.get('room_id')
    total_price = payload.get('total_price')
    service_items = payload.get('services', [])  # list of {service_id, quantity}
    if None in (check_in, check_out, guest_id, room_id, total_price):
        raise HTTPException(status_code=400, detail="Missing required reservation fields")
    # Convert dates from string if needed
    if isinstance(check_in, str):
        check_in = date.fromisoformat(check_in)
    if isinstance(check_out, str):
        check_out = date.fromisoformat(check_out)
    validate_dates(check_in, check_out)
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    # Assume guest count = 1 for simplicity; real logic would derive from payload
    validate_room_capacity(room, guest_count=1)
    reservation = Reservation(check_in=check_in, check_out=check_out, guest_id=guest_id, room_id=room_id, total_price=total_price)
    db.add(reservation)
    db.flush()  # get reservation.id before adding services
    for item in service_items:
        service_id = item.get('service_id')
        quantity = item.get('quantity', 1)
        if service_id is None:
            continue
        rs = ReservationService(reservation_id=reservation.id, service_id=service_id, quantity=quantity)
        db.add(rs)
    db.commit()
    db.refresh(reservation)
    return reservation