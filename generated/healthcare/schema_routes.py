from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from app.db import get_db
from models import Doctor, Patient, Appointment, Prescription


router = APIRouter(prefix="/api/tdm")


@router.get("/doctors")
def list_doctors(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query(Doctor).limit(limit).all()
    return [{col.name: getattr(row, col.name) for col in Doctor.__table__.columns} for row in rows]


@router.post("/doctors")
def create_doctors(data: dict = Body(...), db: Session = Depends(get_db)):
    allowed = {col.name for col in Doctor.__table__.columns if col.name != "id"}
    item = Doctor(**{key: value for key, value in data.items() if key in allowed})
    db.add(item)
    db.commit()
    db.refresh(item)
    return {col.name: getattr(item, col.name) for col in Doctor.__table__.columns}

@router.get("/patients")
def list_patients(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query(Patient).limit(limit).all()
    return [{col.name: getattr(row, col.name) for col in Patient.__table__.columns} for row in rows]


@router.post("/patients")
def create_patients(data: dict = Body(...), db: Session = Depends(get_db)):
    allowed = {col.name for col in Patient.__table__.columns if col.name != "id"}
    item = Patient(**{key: value for key, value in data.items() if key in allowed})
    db.add(item)
    db.commit()
    db.refresh(item)
    return {col.name: getattr(item, col.name) for col in Patient.__table__.columns}

@router.get("/appointments")
def list_appointments(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query(Appointment).limit(limit).all()
    return [{col.name: getattr(row, col.name) for col in Appointment.__table__.columns} for row in rows]


@router.post("/appointments")
def create_appointments(data: dict = Body(...), db: Session = Depends(get_db)):
    allowed = {col.name for col in Appointment.__table__.columns if col.name != "id"}
    item = Appointment(**{key: value for key, value in data.items() if key in allowed})
    db.add(item)
    db.commit()
    db.refresh(item)
    return {col.name: getattr(item, col.name) for col in Appointment.__table__.columns}

@router.get("/prescriptions")
def list_prescriptions(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query(Prescription).limit(limit).all()
    return [{col.name: getattr(row, col.name) for col in Prescription.__table__.columns} for row in rows]


@router.post("/prescriptions")
def create_prescriptions(data: dict = Body(...), db: Session = Depends(get_db)):
    allowed = {col.name for col in Prescription.__table__.columns if col.name != "id"}
    item = Prescription(**{key: value for key, value in data.items() if key in allowed})
    db.add(item)
    db.commit()
    db.refresh(item)
    return {col.name: getattr(item, col.name) for col in Prescription.__table__.columns}
