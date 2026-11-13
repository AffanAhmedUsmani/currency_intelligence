from datetime import datetime, date

from sqlalchemy import create_engine, String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class RateObservation(Base):
    """One daily observation of base->quote exchange rate from a given provider."""

    __tablename__ = "rate_observations"
    __table_args__ = (UniqueConstraint("base", "quote", "obs_date", "provider", name="uq_rate_obs"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(String(8), index=True)
    quote: Mapped[str] = mapped_column(String(8), index=True)
    obs_date: Mapped[date] = mapped_column(Date, index=True)
    rate: Mapped[float] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
