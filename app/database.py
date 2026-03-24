"""SQLAlchemy 非同步資料庫引擎與 Session 管理。"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基礎類別。"""

    pass


async def get_db() -> AsyncSession:
    """取得資料庫 Session（用於 FastAPI Depends）。

    Yields:
        AsyncSession: 資料庫連線 session。
    """
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """初始化資料庫，建立所有資料表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
