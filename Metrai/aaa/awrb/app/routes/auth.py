import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ActivityLog
from app.schemas import UserCreate, UserLogin, UserResponse, Token, ForgotPasswordRequest, ResetPasswordRequest
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def log_activity(db: Session, user_id: Optional[int], action: str, request: Request):
    """Utility to log system activity for auditing and analytics."""
    log = ActivityLog(
        user_id=user_id,
        action=action,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("User-Agent", "unknown")
    )
    db.add(log)
    db.commit()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Registers a new user account, validating email uniqueness and hashing the password."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # First user registered in system becomes the system Administrator automatically
    user_count = db.query(User).count()
    role = "admin" if user_count == 0 else "user"

    # Create new user
    hashed_password = get_password_hash(user_in.password)
    verification_token = f"verify_{create_access_token({'sub': user_in.email})[:20]}"
    
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        role=role,
        is_active=True,
        is_verified=False,  # Set false to simulate email verification structure
        verification_token=verification_token
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_activity(db, new_user.id, "register", request)
    return new_user

@router.post("/login", response_model=Token)
def login(response: Response, request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticates a user, returns a JWT token, and stores it in a secure HTTP-Only cookie."""
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated.")

    # Create JWT
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    
    # Set secure HTTP-Only cookie for template-based frontend authentication
    # Secure=True/False based on settings (enabled in production, disabled for local dev)
    from app.config import settings
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.CSRF_COOKIE_SECURE
    )

    log_activity(db, user.id, "login", request)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Logs out the user, clears secure authentication cookies, and registers the logout activity."""
    response.delete_cookie("access_token")
    log_activity(db, current_user.id, "logout", request)
    return {"detail": "Successfully logged out."}

@router.post("/forgot-password")
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Simulates an email verification and password reset token structure."""
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        reset_token = f"reset_{create_access_token({'sub': user.email})[:20]}"
        user.reset_token = reset_token
        db.commit()
        
        # Log event and simulate mailing
        log_activity(db, user.id, "request_password_reset", request)
        print(f"[MAIL SIMULATION] Sent password reset instructions to {user.email}. Reset Token: {reset_token}")
        
        return {
            "detail": "If the email exists, a password reset link has been dispatched.",
            "reset_token": reset_token, # Returned in dev/API responses to allow easy mock testing
            "simulated": True
        }
    return {"detail": "If the email exists, a password reset link has been dispatched."}

@router.post("/reset-password")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Validates the reset token and updates the user's password."""
    user = db.query(User).filter(User.reset_token == body.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user.hashed_password = get_password_hash(body.new_password)
    user.reset_token = None
    db.commit()
    
    log_activity(db, user.id, "reset_password_success", request)
    return {"detail": "Password has been successfully updated. You can now log in."}

@router.get("/verify/{token}")
def verify_email(token: str, request: Request, db: Session = Depends(get_db)):
    """Verifies a user's email address using the registration token."""
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token.")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    
    log_activity(db, user.id, "verify_email_success", request)
    return {"detail": "Email address successfully verified."}
