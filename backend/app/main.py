import json, secrets, uuid, re
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .agents import assess
from .config import get_settings
from .database import AgentDecision, Base, Device, LinkCode, Parent, RiskEvent, engine, get_db
from .schemas import AnalyzeRequest, AcknowledgeRequest, DeviceCodeRequest, DeviceLinkRequest, LoginRequest, RegisterRequest
from .security import create_token, decode_token, hash_password, verify_password

settings = get_settings()
if settings.environment.lower() == "production" and settings.jwt_secret == "development-only-change-me":
    raise RuntimeError("JWT_SECRET must be replaced before starting in production.")
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Guardian AI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
static_dir = Path(__file__).parent / "static"; app.mount("/static", StaticFiles(directory=static_dir), name="static")

def current_parent(request: Request, db: Session = Depends(get_db)) -> Parent:
    raw = request.headers.get("Authorization", "").removeprefix("Bearer ")
    parent_id = decode_token(raw); parent = db.get(Parent, parent_id) if parent_id else None
    if not parent: raise HTTPException(401, "Valid parent authentication is required.")
    return parent

def alert_dict(event: RiskEvent):
    return {"id":event.id,"source":event.source,"category":event.category,"severity":event.severity,"score":event.score,"confidence":event.confidence,"trigger_text":event.trigger_text,"context":json.loads(event.context_text),"rationale":event.rationale,"acknowledged":event.acknowledged,"created_at":event.created_at}

def canonical_trigger(text: str) -> str:
    """Create a short fingerprint so DOM metadata does not create duplicate alerts."""
    value = re.sub(r"\s+", " ", text.casefold()).strip()
    # WhatsApp selectors can append the rendered message time to the text.
    return re.sub(r"\s+\d{1,2}:\d{2}(?:\s*[ap]m)?$", "", value).strip()

def unique_alert_rows(rows: list[RiskEvent]) -> list[RiskEvent]:
    """Keep the newest copy of each active signal per device and category."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[RiskEvent] = []
    for row in rows:
        key = (row.device_id, row.category, canonical_trigger(row.trigger_text))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique

@app.on_event("startup")
def seed_demo():
    if settings.environment.lower() == "production":
        return
    db = next(get_db())
    try:
        if not db.query(Parent).filter_by(email=settings.demo_email).first():
            db.add(Parent(name="Demo Parent", email=settings.demo_email, password_hash=hash_password(settings.demo_password))); db.commit()
    finally: db.close()

@app.get("/")
def dashboard(): return FileResponse(static_dir / "index.html")

@app.get("/privacy")
def privacy(): return FileResponse(static_dir / "privacy.html")

@app.get("/health")
def health():
    provider = settings.ai_provider.lower()
    return {
        "status": "ok",
        "service": "guardian-ai",
        "analysis_provider": provider,
        "semantic_ai_enabled": provider == "openai" and bool(settings.openai_api_key),
    }

@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    parent = db.query(Parent).filter_by(email=payload.email.lower()).first()
    if not parent or not verify_password(payload.password, parent.password_hash): raise HTTPException(401, "Incorrect email or password.")
    return {"access_token":create_token(parent.id), "token_type":"bearer", "parent":{"name":parent.name,"email":parent.email}}

@app.post("/api/v1/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Enter a valid email address.")
    if not re.search(r"[A-Za-z]", payload.password) or not re.search(r"\d", payload.password):
        raise HTTPException(422, "Password must contain letters and numbers and be at least 12 characters.")
    parent = Parent(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(parent)
    try:
        db.commit(); db.refresh(parent)
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "An account with that email already exists.")
    return {"access_token":create_token(parent.id), "token_type":"bearer", "parent":{"name":parent.name,"email":parent.email}}

@app.post("/api/v1/devices/codes")
def create_code(payload: DeviceCodeRequest, parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    code = secrets.token_hex(3).upper(); db.add(LinkCode(code=code, parent_id=parent.id, expires_at=datetime.utcnow()+timedelta(minutes=15))); db.commit()
    return {"code":code,"expires_in_minutes":15,"label":payload.label}

@app.post("/api/v1/devices/link")
def link_device(payload: DeviceLinkRequest, db: Session = Depends(get_db)):
    link = db.get(LinkCode, payload.code.strip().upper())
    if not link or link.used or link.expires_at < datetime.utcnow(): raise HTTPException(400, "That link code is invalid or expired.")
    device = Device(id=str(uuid.uuid4()), parent_id=link.parent_id, label=payload.label); link.used=True; db.add(device); db.commit()
    return {"device_id":device.id,"status":"linked"}

@app.get("/api/v1/devices")
def list_devices(parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    return [{"id":d.id,"label":d.label,"status":d.status,"created_at":d.created_at} for d in db.query(Device).filter_by(parent_id=parent.id).all()]

@app.delete("/api/v1/devices/{device_id}")
def revoke_device(device_id: str, parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id, Device.parent_id == parent.id).first()
    if not device: raise HTTPException(404, "Device not found.")
    device.status = "revoked"
    db.commit()
    return {"device_id": device.id, "status": "revoked"}

@app.post("/api/v1/devices/reset")
def reset_devices(parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.parent_id == parent.id).all()
    for device in devices: device.status = "revoked"
    db.query(LinkCode).filter(LinkCode.parent_id == parent.id, LinkCode.used == False).update({"used": True})
    db.commit()
    return {"revoked": len(devices)}

@app.post("/api/v1/analyze")
def analyze(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    device = db.get(Device, payload.device_id)
    if not device or device.status != "linked": raise HTTPException(404, "Linked device not found.")
    trigger_text = payload.text.strip()
    fingerprint = canonical_trigger(trigger_text)
    duplicate_cutoff = datetime.utcnow() - timedelta(seconds=30)
    recent_events = db.query(RiskEvent).filter(
        RiskEvent.device_id == device.id,
        RiskEvent.source == payload.source,
        RiskEvent.created_at >= duplicate_cutoff,
    ).order_by(RiskEvent.created_at.desc()).all()
    duplicate = next((event for event in recent_events if canonical_trigger(event.trigger_text) == fingerprint), None)
    if duplicate:
        return {
            "risk": duplicate.severity.lower(),
            "score": duplicate.score,
            "category": duplicate.category,
            "confidence": duplicate.confidence,
            "alert_created": False,
            "deduplicated": True,
            "event_id": duplicate.id,
        }
    history = db.query(RiskEvent).filter(RiskEvent.device_id==device.id, RiskEvent.created_at >= datetime.utcnow()-timedelta(hours=24)).order_by(RiskEvent.created_at).all()
    result = assess(trigger_text, history)
    if result.category == "normal": return {"risk":"low","score":0,"category":"normal","alert_created":False,"data_retained":False}
    event = RiskEvent(id=str(uuid.uuid4()), device_id=device.id, source=payload.source, category=result.category, severity=result.severity, score=result.score, confidence=result.confidence, trigger_text=trigger_text, context_text=json.dumps(result.context), rationale=result.rationale)
    db.add(event); db.flush()
    db.add_all([AgentDecision(risk_event_id=event.id, agent_name=name, decision=decision, reason=reason) for name,decision,reason in result.decisions]); db.commit()
    return {"risk":result.severity.lower(),"score":result.score,"category":result.category,"confidence":result.confidence,"alert_created":result.alert,"event_id":event.id}

@app.get("/api/v1/alerts")
def list_alerts(parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    rows = db.query(RiskEvent).join(Device).filter(Device.parent_id==parent.id, RiskEvent.severity.in_(["HIGH","CRITICAL"]), RiskEvent.acknowledged == False).order_by(RiskEvent.created_at.desc()).all()
    return [alert_dict(row) for row in unique_alert_rows(rows)]

@app.get("/api/v1/alerts/history")
def alert_history(parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    rows = db.query(RiskEvent).join(Device).filter(Device.parent_id==parent.id, RiskEvent.severity.in_(["HIGH","CRITICAL"]), RiskEvent.acknowledged == True).order_by(RiskEvent.created_at.desc()).all()
    return [alert_dict(row) for row in unique_alert_rows(rows)]

@app.get("/api/v1/alerts/{alert_id}")
def get_alert(alert_id: str, parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    row = db.query(RiskEvent).join(Device).filter(RiskEvent.id==alert_id, Device.parent_id==parent.id).first()
    if not row: raise HTTPException(404, "Alert not found.")
    return {**alert_dict(row), "decisions":[{"agent":d.agent_name,"decision":d.decision,"reason":d.reason,"created_at":d.created_at} for d in row.decisions]}

@app.post("/api/v1/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str, payload: AcknowledgeRequest, parent: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    row = db.query(RiskEvent).join(Device).filter(RiskEvent.id==alert_id, Device.parent_id==parent.id).first()
    if not row: raise HTTPException(404, "Alert not found.")
    row.acknowledged=payload.acknowledged; db.commit(); return alert_dict(row)
