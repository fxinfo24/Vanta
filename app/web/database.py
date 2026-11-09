"""
Vanta Database Configuration
Enhanced database setup with SQLAlchemy for production use
"""

import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.utils.config import database_uri

# Load environment variables
load_dotenv()

# Same resolution rules as the Flask factory (postgres:// alias, psycopg2 driver,
# mandatory SSL, relative SQLite anchored to the project root). Duplicating that
# logic here is how a second engine ends up pointing at a different database.
DATABASE_URL = database_uri("sqlite:///data/vanta.db")

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False},  # For SQLite
        echo=False
    )
else:
    # pool_pre_ping: a pooled endpoint may have dropped this connection while idle.
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=280)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()

def get_database_session():
    """Get database session"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")

def get_engine():
    """Get database engine"""
    return engine

# Metadata for table introspection
metadata = MetaData()