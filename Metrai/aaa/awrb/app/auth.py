import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import TokenData

# CryptContext for password hashing and verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Reusable OAuth2 password bearer scheme for API requests
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies that a plain text password matches its hashed equivalent."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hashes a password secure using BCrypt."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Generates a secure JSON Web Token with expiration claims."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def extract_token_from_request(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """
    Hybrid token extractor that retrieves JWT either from the standard Authorization header
    or from secure browser session cookies. Enables seamless API & UI interaction.
    """
    if token:
        return token
    # Try cookies for Jinja templates rendering
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Expected format: "Bearer <token>" or simply "<token>"
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token
    return None

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency injector that authenticates a request using standard headers or cookies.
    Returns the authenticated User model.
    """
    token = extract_token_from_request(request, request.headers.get("Authorization"))
    if not token:
        # Check OAuth2 default format
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials, please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email, role=role)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensures the authenticated user account is in an active state."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account.")
    return current_user

def get_current_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Authorization layer ensuring the authenticated active user is an administrator."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Admin privilege required."
        )
    return current_user

def get_optional_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Fetches the user if credentials are supplied (for tracking history, saving, custom state),
    but returns None instead of raising errors for guest actions.
    """
    try:
        token = extract_token_from_request(request)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            return None
            
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
            
        return db.query(User).filter(User.email == email).first()
    except Exception:
        return None
