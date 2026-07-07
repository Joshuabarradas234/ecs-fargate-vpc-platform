"""
FastAPI application for the ECS Fargate VPC platform.

Endpoints:
  GET  /health  -> liveness probe used by the ALB target group and ECS
  GET  /items   -> list items from PostgreSQL
  POST /items   -> insert an item into PostgreSQL

Database configuration is read from environment variables at runtime.
In AWS, the DB credentials are injected from Secrets Manager via the ECS
task definition (never hardcoded). Locally, they come from a .env / env vars.
"""

import os
from contextlib import asynccontextmanager, contextmanager
from typing import Generator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# psycopg is imported lazily inside get_connection so the app module can be
# imported (and unit-tested) in environments without a database driver present.


@asynccontextmanager
async def lifespan(_app: "FastAPI"):
    """
    Best-effort table creation on startup.

    If the DB is not reachable yet (e.g. during a rolling deploy), don't crash
    the app — /health must still return 200 so the ALB keeps the task alive.
    """
    if os.environ.get("SKIP_DB_INIT", "").lower() not in ("1", "true", "yes"):
        try:
            init_db()
        except Exception:
            # Printed to stdout; the awslogs driver ships it to CloudWatch.
            print("startup: init_db failed; will retry on first DB request")
    yield


app = FastAPI(
    title="ECS Fargate VPC Platform API",
    description="A small REST API demonstrating internet -> ALB -> ECS -> RDS.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ItemIn(BaseModel):
    """Payload for creating an item."""

    name: str = Field(..., min_length=1, max_length=255)


class ItemOut(BaseModel):
    """Item as returned to the client."""

    id: int
    name: str


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _db_config() -> dict:
    """Build DB connection config from environment variables."""
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "appdb"),
        "user": os.environ.get("DB_USER", "appuser"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "5")),
    }


@contextmanager
def get_connection() -> Generator[object, None, None]:
    """
    Yield a psycopg connection, closing it afterwards.

    Imported lazily so the module can be imported without psycopg installed
    (unit tests patch this function and never open a real connection).
    """
    import psycopg  # local import keeps app importable without the driver

    conn = psycopg.connect(**_db_config())
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the items table if it does not exist. Called on startup."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id   SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL
                )
                """
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    """Liveness probe. Must be fast and dependency-free (no DB call)."""
    return {"status": "ok"}


@app.get("/items", response_model=list[ItemOut])
def list_items() -> list[ItemOut]:
    """Return all items from the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM items ORDER BY id")
                rows = cur.fetchall()
        return [ItemOut(id=row[0], name=row[1]) for row in rows]
    except Exception as exc:  # surface DB errors as 503, not 500 stack traces
        raise HTTPException(status_code=503, detail="database unavailable") from exc


@app.post("/items", response_model=ItemOut, status_code=201)
def create_item(item: ItemIn) -> ItemOut:
    """Insert an item and return it with its generated id."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO items (name) VALUES (%s) RETURNING id",
                    (item.name,),
                )
                new_id = cur.fetchone()[0]
            conn.commit()
        return ItemOut(id=new_id, name=item.name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
