from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

attendance_services = Table(
    "attendance_services",
    Base.metadata,
    Column("attendance_id", Integer, ForeignKey("attendances.id"), primary_key=True),
    Column("service_id", Integer, ForeignKey("services.id"), primary_key=True),
)

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    cpf = Column(String(14), unique=True, nullable=False, index=True)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    email = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relacionamentos
    attendances = relationship("Attendance", back_populates="client")

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    duration_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Attendance(Base):
    __tablename__ = "attendances"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    # Mantido para compatibilidade, mas o relacionamento principal passa a ser muitos-para-muitos via attendance_services
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    appointment_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="waiting")  # waiting, progress, finished, cancelled
    payment_method = Column(String(50), nullable=True)  # cash, card, pix
    payment_status = Column(String(20), default="pending")  # pending, paid, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    client = relationship("Client", back_populates="attendances")
    service = relationship("Service")
    services = relationship("Service", secondary=attendance_services)