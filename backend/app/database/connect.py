from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# Create engine with multi-threaded access
engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} ## is SQLite-specific and will cause problems if DATABASE_URL points to PostgreSQL. Use it only for SQLite.
)

# Async session factory - each call creates a new DB session bound to the engine
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for all ORM models to inherit from
class Base(DeclarativeBase):
    pass

# Async dependency that yoelds a DB session and closes it after the request
# Used directly when FastAPI is resolving dependencies for an HTTP route
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
