from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, CalculationHistory, ActivityLog, AdminReport
from app.auth import get_optional_user
import os

router = APIRouter(tags=["HTML Page Renderers"])

# Locate the templates directory relative to this file
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def get_current_user_from_cookie(request: Request, db: Session) -> Optional[User]:
    """Helper to retrieve user details from browser session cookies for page rendering."""
    cookie_token = request.cookies.get("access_token")
    if not cookie_token:
        return None
        
    try:
        # Extract Bearer token prefix if present
        token = cookie_token[7:] if cookie_token.startswith("Bearer ") else cookie_token
        from jose import jwt
        from app.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            return None
        return db.query(User).filter(User.email == email).first()
    except Exception:
        return None

@router.get("/")
def view_home(request: Request, db: Session = Depends(get_db)):
    """Renders the Metrai Calculus interactive landing page."""
    user = get_current_user_from_cookie(request, db)
    return templates.TemplateResponse("home.html", {"request": request, "user": user, "page": "home"})

@router.get("/login")
def view_login(request: Request, db: Session = Depends(get_db)):
    """Renders the glassmorphic login panel. Redirects active sessions to dashboard."""
    user = get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "page": "login"})

@router.get("/register")
def view_register(request: Request, db: Session = Depends(get_db)):
    """Renders the sleek registration page. Redirects active sessions."""
    user = get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("register.html", {"request": request, "user": None, "page": "register"})

@router.get("/dashboard")
def view_dashboard(request: Request, db: Session = Depends(get_db)):
    """Renders the central workspace dashboard. Requires authenticated user session."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login?error=Session expired, please log in.", status_code=status.HTTP_303_SEE_OTHER)
        
    # Fetch recent calculation history
    history = db.query(CalculationHistory)\
        .filter(CalculationHistory.user_id == user.id)\
        .order_by(CalculationHistory.created_at.desc())\
        .limit(20)\
        .all()
        
    # Fetch pinned calculations
    pinned = db.query(CalculationHistory)\
        .filter(CalculationHistory.user_id == user.id, CalculationHistory.is_saved == True)\
        .order_by(CalculationHistory.created_at.desc())\
        .all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "history": history,
        "pinned": pinned,
        "page": "dashboard"
    })

@router.get("/calculator")
def view_calculator(request: Request, db: Session = Depends(get_db)):
    """Renders the advanced full scientific and calculus mathematical solver console."""
    user = get_current_user_from_cookie(request, db)
    return templates.TemplateResponse("calculator.html", {"request": request, "user": user, "page": "calculator"})

@router.get("/ocr")
def view_ocr(request: Request, db: Session = Depends(get_db)):
    """Renders the Image Recognition equation-scanner workspace (upload & canvas solver)."""
    user = get_current_user_from_cookie(request, db)
    return templates.TemplateResponse("ocr.html", {"request": request, "user": user, "page": "ocr"})

@router.get("/profile")
def view_profile(request: Request, db: Session = Depends(get_db)):
    """Renders the profile details and safety credentials edit console."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login?error=Please log in to manage your profile.", status_code=status.HTTP_303_SEE_OTHER)
        
    # Calculate account age
    days_member = (datetime.datetime.utcnow() - user.created_at).days + 1
    
    # Calculate totals
    calc_count = db.query(CalculationHistory).filter(CalculationHistory.user_id == user.id).count()
    report_count = db.query(AdminReport).filter(AdminReport.reporter_id == user.id).count()

    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "user": user,
        "days_member": days_member,
        "calc_count": calc_count,
        "report_count": report_count,
        "page": "profile"
    })

@router.get("/admin")
def view_admin(request: Request, db: Session = Depends(get_db)):
    """Renders the system-wide telemetry panel, user editor, and report manager. Requires Admin role."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login?error=Please log in to view this page.", status_code=status.HTTP_303_SEE_OTHER)
        
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: System administrator privilege required."
        )

    # Pre-fetch administrative statistics to render instantly
    total_users = db.query(User).count()
    total_calculations = db.query(CalculationHistory).count()
    open_reports = db.query(AdminReport).filter(AdminReport.status == "open").count()
    
    users = db.query(User).order_by(User.created_at.desc()).all()
    reports = db.query(AdminReport).order_by(AdminReport.created_at.desc()).all()
    recent_logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(15).all()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "users": users,
        "reports": reports,
        "logs": recent_logs,
        "total_users": total_users,
        "total_calculations": total_calculations,
        "open_reports": open_reports,
        "page": "admin"
    })
