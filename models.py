from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Float, func
from database import Base

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    device_id = Column(String(100), nullable=False)
    status = Column(String(20), default="pending", nullable=False) # pending, active, blocked
    expiry_date = Column(Date, nullable=True)
    min_fare = Column(Integer, default=100, nullable=False)
    max_fare = Column(Integer, default=1500, nullable=False)
    max_distance = Column(Float, default=5.0, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_tester = Column(Boolean, default=False, nullable=False)
    password = Column(String(100), nullable=True)
    vehicle_number = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    language = Column(String(10), default="mr", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class RideLog(Base):
    __tablename__ = "ride_logs"

    id = Column(Integer, primary_key=True, index=True)
    driver_phone = Column(String(20), index=True, nullable=False)
    platform = Column(String(50), nullable=False) # Ola, Uber, Rapido, Namma Yatri
    fare = Column(Integer, nullable=False)
    pickup = Column(String(255), nullable=True)
    drop = Column(String(255), nullable=True)
    distance = Column(Float, nullable=True)
    status = Column(String(20), nullable=False) # accepted, skipped
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
