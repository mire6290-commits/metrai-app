from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# For SQLite, check_same_thread: False is needed as FastAPI handles requests concurrently in different threads
connect_args = {}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True  # Detect and recover dropped connections (essential in prod)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Database session dependency injector.
    Yields a session and safely closes it when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
