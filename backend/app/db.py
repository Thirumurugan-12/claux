"""Database engine and session management.

Note the search_path: `ksp` (source tables) and `derived` (everything we compute)
are separate schemas. Queries can name tables unqualified, but prefer explicit
`ksp.` / `derived.` prefixes in tool SQL so it is obvious which side you are reading.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"options": "-csearch_path=ksp,derived,public"},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_connection() -> dict[str, object]:
    """Health probe: confirms the database is reachable and the schema is present."""
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
        postgis = conn.execute(text("SELECT PostGIS_Version()")).scalar_one()
        ksp_tables = conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'ksp'")
        ).scalar_one()
        derived_tables = conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'derived'")
        ).scalar_one()

    return {
        "postgres": version.split(",")[0],
        "postgis": postgis,
        "ksp_tables": ksp_tables,
        "derived_tables": derived_tables,
    }
