# models.py
from sqlalchemy import Column, Float, Integer, String, ForeignKey, LargeBinary, DateTime, Boolean
from sqlalchemy.orm import relationship
from db import Base
from datetime import datetime

class Person(Base):
    __tablename__ = "person"
    id = Column(Integer, primary_key=True, index=True)
    
    salutation = Column(String, nullable=False)
    title = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    second_name = Column(String, nullable=False)
    street = Column(String, nullable=False)
    house_number = Column(String, nullable=False)
    zip_code = Column(String, nullable=False)
    city = Column(String, nullable=False)
    country = Column(String, nullable=False)
    person_type = Column(String, nullable=False)  # admin / employee / customer / manager / director
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    reset_token = Column(String, nullable=True)
    reset_token_expiration = Column(DateTime, nullable=True)

    # A Person can have many Applications
    applications = relationship(
        "Application",
        back_populates="person",
        foreign_keys="[Application.person_id]",
        cascade="all, delete-orphan"
    )

    # A Person can have many Files
    files = relationship(
        "File",
        back_populates="person",
        cascade="all, delete-orphan"
    )

    # Notifications received by this user
    notifications = relationship(
        "Notification",
        back_populates="recipient",
        foreign_keys="[Notification.recipient_id]",
        cascade="all, delete-orphan"
    )

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    loan_type = Column(String, nullable=False)
    loan_subtype = Column(String, nullable=False)
    requested_amount = Column(Integer, nullable=False)
    term_in_years = Column(Integer, nullable=False)
    repayment_amount = Column(Integer, nullable=True)
    status = Column(String, default="in_process")
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    # The user who handled this request (admin or employee)
    handled_by_id = Column(Integer, ForeignKey("person.id"), nullable=True)

    dscr = Column(Float, nullable=True)      
    ccr = Column(Float, nullable=True)        
    bonitaet = Column(String, nullable=True)  

    decision = Column(String, nullable=True)  
    reason = Column(String, nullable=True)
    
    interest_rate = Column(Float, default=5.0)  # Default 5%
    monthly_payment = Column(Float, nullable=True)
    
    # Manager approval fields
    needs_manager_approval = Column(Boolean, default=False)
    manager_approved = Column(Boolean, nullable=True)
    manager_id = Column(Integer, ForeignKey("person.id"), nullable=True)
    manager_notes = Column(String, nullable=True)
    
    # Offer related fields
    offer_created = Column(Boolean, default=False)
    offer_sent = Column(Boolean, default=False)
    offer_accepted = Column(Boolean, default=False)
    
    # Relationship to the Person who owns this application
    person = relationship(
        "Person",
        back_populates="applications",
        foreign_keys=[person_id]
    )
    
    # Relationship to the Person who last handled this application
    handled_by = relationship(
        "Person",
        foreign_keys=[handled_by_id]
    )
    
    # Relationship to the manager who approved/rejected this application
    manager = relationship(
        "Person",
        foreign_keys=[manager_id]
    )

    # Relationship to Files
    files = relationship(
        "File",
        back_populates="application",
        cascade="all, delete-orphan"
    )

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_data = Column(LargeBinary, nullable=False)

    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)

    # Relationship back to Application
    application = relationship("Application", back_populates="files")

    # Relationship back to Person
    person = relationship("Person", back_populates="files")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("person.id"), nullable=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)
    notification_type = Column(String, default="info")  # info, warning, approval_request
    
    # Relationships
    recipient = relationship("Person", foreign_keys=[recipient_id], back_populates="notifications")
    sender = relationship("Person", foreign_keys=[sender_id])
    application = relationship("Application")