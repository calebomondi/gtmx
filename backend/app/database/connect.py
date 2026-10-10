from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# pool_pre_ping drops connections the server (or Supabase's pooler) closed
# while idle, instead of failing the next request on a dead socket.
engine = create_async_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
)

# Each call creates a new session bound to the engine.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# FastAPI dependency: one session per request, closed afterwards.
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
