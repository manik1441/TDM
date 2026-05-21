from sqlalchemy import Column, String, Integer, Float, ForeignKey, Text, Date, Boolean
from sqlalchemy.orm import relationship
from app.db import Base


class Hotel(Base):
    __tablename__ = 'hotels'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)  # 1 to 5, enforce in app logic

    rooms = relationship('Room', back_populates='hotel', cascade='all, delete-orphan')
    services = relationship('Service', back_populates='hotel', cascade='all, delete-orphan')


class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)  # must be >= guests in a reservation
    price_per_night = Column(Float, nullable=False)
    hotel_id = Column(Integer, ForeignKey('hotels.id'), nullable=False)

    hotel = relationship('Hotel', back_populates='rooms')
    reservations = relationship('Reservation', back_populates='room', cascade='all, delete-orphan')


class Guest(Base):
    __tablename__ = 'guests'
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    phone = Column(String, nullable=True)

    reservations = relationship('Reservation', back_populates='guest', cascade='all, delete-orphan')


class Service(Base):
    __tablename__ = 'services'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    charge = Column(Float, nullable=False)  # non‑negative, enforce in app logic
    hotel_id = Column(Integer, ForeignKey('hotels.id'), nullable=False)

    hotel = relationship('Hotel', back_populates='services')
    reservations = relationship('ReservationService', back_populates='service', cascade='all, delete-orphan')


class Reservation(Base):
    __tablename__ = 'reservations'
    id = Column(Integer, primary_key=True, index=True)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    guest_id = Column(Integer, ForeignKey('guests.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    total_price = Column(Float, nullable=False)

    guest = relationship('Guest', back_populates='reservations')
    room = relationship('Room', back_populates='reservations')
    services = relationship('ReservationService', back_populates='reservation', cascade='all, delete-orphan')


class ReservationService(Base):
    __tablename__ = 'reservation_services'
    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey('reservations.id'), nullable=False)
    service_id = Column(Integer, ForeignKey('services.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    reservation = relationship('Reservation', back_populates='services')
    service = relationship('Service', back_populates='reservations')