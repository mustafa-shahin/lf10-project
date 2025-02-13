from sqlalchemy import Column, Integer, String, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from db import Base

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
    person_type = Column(String, default="customer")

    # One-to-one relationship: one Application per Person.
    application = relationship(
        "Application",
        back_populates="person",
        uselist=False,
        cascade="all, delete-orphan"
    )

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False, unique=True)
    loan_type = Column(String, nullable=False)
    loan_subtype = Column(String, nullable=False)
    requested_amount = Column(Integer, nullable=False)
    term_in_years = Column(Integer, nullable=False)

    person = relationship("Person", back_populates="application")
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

    application = relationship("Application", back_populates="files")
