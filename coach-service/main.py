from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import requests, os

from database import Base, engine, get_db
from models import Coach, CoachTeam
from schemas import CoachCreate, CoachOut, TeamRef

Base.metadata.create_all(bind=engine)

app = FastAPI(title="coach-service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

BD_URL = os.environ.get("BD_SERVICE_URL", "http://bd:3001")

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/teams")
def list_teams():
    """Lista equipos disponibles desde la BD BOCA (vía bd-service)."""
    r = requests.post(f"{BD_URL}/api/query", json={
        "host": "postgres", "port": 5432, "user": "postgres", "password": "1234",
        "query": "SELECT usernumber, userfullname, country FROM usertable WHERE usertype='team' ORDER BY userfullname;"
    }, timeout=10)
    r.raise_for_status()
    return r.json().get("rows", [])

@app.post("/coaches", response_model=CoachOut)
def create_coach(payload: CoachCreate, db: Session = Depends(get_db)):
    if db.query(Coach).filter(Coach.login == payload.login).first():
        raise HTTPException(400, "login ya existe")
    if db.query(Coach).filter(Coach.email == payload.email).first():
        raise HTTPException(400, "email ya existe")
    coach = Coach(
        nombre=payload.nombre, apellido=payload.apellido, login=payload.login,
        password_hash=pwd.hash(payload.password), email=payload.email,
        pais=payload.pais, universidad=payload.universidad,
    )
    for t in payload.teams:
        coach.teams.append(CoachTeam(team_usernumber=t.usernumber, team_fullname=t.fullname))
    db.add(coach); db.commit(); db.refresh(coach)
    return _to_out(coach)

@app.get("/coaches", response_model=list[CoachOut])
def list_coaches(db: Session = Depends(get_db)):
    return [_to_out(c) for c in db.query(Coach).all()]

@app.get("/coaches/{coach_id}", response_model=CoachOut)
def get_coach(coach_id: int, db: Session = Depends(get_db)):
    c = db.query(Coach).get(coach_id)
    if not c: raise HTTPException(404, "no existe")
    return _to_out(c)

def _to_out(c: Coach) -> CoachOut:
    return CoachOut(
        id=c.id, nombre=c.nombre, apellido=c.apellido, login=c.login,
        email=c.email, pais=c.pais, universidad=c.universidad,
        teams=[TeamRef(usernumber=t.team_usernumber, fullname=t.team_fullname) for t in c.teams],
    )
