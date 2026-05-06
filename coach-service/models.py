from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Coach(Base):
    __tablename__ = "coaches"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    apellido = Column(String(80), nullable=False)
    login = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    pais = Column(String(60), nullable=False)
    universidad = Column(String(120), nullable=False)
    teams = relationship("CoachTeam", back_populates="coach", cascade="all, delete-orphan")

class CoachTeam(Base):
    __tablename__ = "coach_teams"
    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    team_usernumber = Column(Integer, nullable=False)
    team_fullname = Column(String(200), nullable=False)
    coach = relationship("Coach", back_populates="teams")
