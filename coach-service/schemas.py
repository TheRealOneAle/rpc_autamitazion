from pydantic import BaseModel, EmailStr
from typing import List

class TeamRef(BaseModel):
    usernumber: int
    fullname: str

class CoachCreate(BaseModel):
    nombre: str
    apellido: str
    login: str
    password: str
    email: EmailStr
    pais: str
    universidad: str
    teams: List[TeamRef]

class CoachOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    login: str
    email: EmailStr
    pais: str
    universidad: str
    teams: List[TeamRef]
    class Config:
        from_attributes = True
