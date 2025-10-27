"""
Database connection and session management for YouTube Audit Engine.

This module provides SQLAlchemy database connection, session factory,
and base model class for all database models.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from backend.config import get_config
from backend.utils.logging_config import get_logger

log = get_logger(__name__)

# Global database engine and session factory
_engine = None
_SessionLocal = None

# Base class for all models
Base = declarative_base()


def get_engine():
    """
    Get the SQLAlchemy engine (singleton).

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine

    if _engine is None:
        config = get_config()

        log.info(
            "Creating database engine",
            database_url=config.database_url.split('@')[-1],  # Hide credentials in logs
            pool_size=config.database_pool_size,
            max_overflow=config.database_max_overflow
        )

        _engine = create_engine(
            config.database_url,
            pool_size=config.database_pool_size,
            max_overflow=config.database_max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=config.is_development(),  # Log SQL in development
        )

        log.info("Database engine created successfully")

    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get the session factory.

    Returns:
        SQLAlchemy sessionmaker
    """
    global _SessionLocal

    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
        log.info("Database session factory created")

    return _SessionLocal


def get_session() -> Session:
    """
    Get a new database session.

    Returns:
        SQLAlchemy Session (must be closed by caller)

    Example:
        >>> from backend.database import get_session
        >>> session = get_session()
        >>> try:
        ...     # Use session
        ...     session.query(Analysis).all()
        ...     session.commit()
        ... finally:
        ...     session.close()
    """
    SessionLocal = get_session_factory()
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """
    Get a database session (dependency injection for FastAPI/Flask).

    Yields:
        SQLAlchemy Session

    Example:
        >>> from backend.database import get_db
        >>> db = next(get_db())
        >>> try:
        ...     # Use db session
        ...     db.query(Analysis).all()
        ... finally:
        ...     db.close()
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Create all database tables.

    This should be called on application startup or via migrations.
    """
    log.info("Creating database tables")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    log.info("Database tables created successfully")


def drop_tables():
    """
    Drop all database tables.

    WARNING: This will delete all data! Only use in development/testing.
    """
    config = get_config()
    if config.is_production():
        raise RuntimeError("Cannot drop tables in production environment")

    log.warning("Dropping all database tables")
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    log.warning("All database tables dropped")


def health_check() -> bool:
    """
    Check if database is healthy.

    Returns:
        True if database is responsive, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        return True
    except Exception as e:
        log.error("Database health check failed", error=str(e))
        return False


def close_connections():
    """
    Close all database connections.

    This should be called on application shutdown.
    """
    global _engine

    if _engine is not None:
        log.info("Closing database connections")
        _engine.dispose()
        _engine = None
