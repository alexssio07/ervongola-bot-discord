"""
Persistenza film su SQLite, con sqlite3 della standard library — nessuna
dipendenza ORM: una tabella sola non giustifica SQLAlchemy, e per un
pannello a bassa concorrenza (un singolo admin) query parametrizzate dirette
restano più semplici da leggere e mantenere.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATABASE_PATH

VALID_STATUSES = ("visto", "da_guardare")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'da_guardare',
                cover_url TEXT NOT NULL DEFAULT '',
                genre TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Utenti registrati dal form pubblico di registrazione (vedi
        # auth.py/auth_routes.py): coesistono con l'admin "fisso" definito
        # via ADMIN_USERNAME/ADMIN_PASSWORD_HASH nelle env var, che resta
        # valido esattamente come prima e non passa da questa tabella.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _movies_where(status: str | None, platform: str | None, genre: str | None, search: str | None) -> tuple[str, list]:
    """Clausola WHERE condivisa da list_movies e count_movies, per non
    duplicare gli stessi filtri in due punti (e rischiare che finiscano per
    divergere in una futura modifica)."""
    clause = "WHERE 1=1"
    params: list = []

    if status:
        clause += " AND status = ?"
        params.append(status)
    if platform:
        clause += " AND platform LIKE ? COLLATE NOCASE"
        params.append(f"%{platform}%")
    if genre:
        clause += " AND genre LIKE ? COLLATE NOCASE"
        params.append(f"%{genre}%")
    if search:
        clause += " AND (title LIKE ? COLLATE NOCASE OR notes LIKE ? COLLATE NOCASE)"
        like = f"%{search}%"
        params.extend([like, like])

    return clause, params


def count_movies(status: str | None, platform: str | None, genre: str | None, search: str | None) -> int:
    clause, params = _movies_where(status, platform, genre, search)
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM movies {clause}", params)
        return cur.fetchone()["c"]


def list_movies(
    status: str | None,
    platform: str | None,
    genre: str | None,
    search: str | None,
    page: int = 1,
    page_size: int = 12,
) -> list[dict]:
    clause, params = _movies_where(status, platform, genre, search)
    offset = max(page - 1, 0) * page_size
    query = f"SELECT * FROM movies {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"

    with db_cursor() as cur:
        cur.execute(query, params + [page_size, offset])
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_movie(movie_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def create_movie(data: dict) -> dict:
    now = _now()
    status = data.get("status") or "da_guardare"
    if status not in VALID_STATUSES:
        raise ValueError(f"Stato non valido: {status}")

    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO movies (title, link, platform, status, cover_url, genre, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["title"].strip(),
                data.get("link", "").strip(),
                data.get("platform", "").strip(),
                status,
                data.get("cover_url", "").strip(),
                data.get("genre", "").strip(),
                data.get("notes", "").strip(),
                now,
                now,
            ),
        )
        new_id = cur.lastrowid

    return get_movie(new_id)


def update_movie(movie_id: int, data: dict) -> dict | None:
    existing = get_movie(movie_id)
    if existing is None:
        return None

    if "status" in data and data["status"] not in VALID_STATUSES:
        raise ValueError(f"Stato non valido: {data['status']}")

    fields = ["title", "link", "platform", "status", "cover_url", "genre", "notes"]
    updates = {f: data[f] for f in fields if f in data}
    if not updates:
        return existing

    set_clause = ", ".join(f"{f} = ?" for f in updates)
    params = list(updates.values()) + [_now(), movie_id]

    with db_cursor() as cur:
        cur.execute(
            f"UPDATE movies SET {set_clause}, updated_at = ? WHERE id = ?",
            params,
        )

    return get_movie(movie_id)


def delete_movie(movie_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        return cur.rowcount > 0


def get_user_by_username(username: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def create_user(username: str, password_hash: str) -> dict:
    """Solleva ValueError se lo username è già in uso (vincolo UNIQUE sulla
    colonna, non un controllo separato: evita una finestra di race fra un
    controllo 'esiste già?' e l'INSERT vero e proprio)."""
    now = _now()
    with db_cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, now),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError("Questo username è già in uso.") from e

    return get_user_by_username(username)
