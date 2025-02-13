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

    # ONE Person -> MANY Applications
    applications = relationship(
        "Application",
        back_populates="person",
        cascade="all, delete-orphan"
    )

    # ONE Person -> MANY Files
    files = relationship(
        "File",
        back_populates="person",
        cascade="all, delete-orphan"
    )

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    # Drop unique=True, since one person can now have multiple applications
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)

    loan_type = Column(String, nullable=False)
    loan_subtype = Column(String, nullable=False)
    requested_amount = Column(Integer, nullable=False)
    term_in_years = Column(Integer, nullable=False)

    # MANY Applications -> ONE Person
    person = relationship("Person", back_populates="applications")

    # ONE Application -> MANY Files
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

    # MANY Files -> ONE Application
    application = relationship("Application", back_populates="files")

    # MANY Files -> ONE Person
    person = relationship("Person", back_populates="files")
