"""
Persistenza film su SQLite, con sqlite3 della standard library — nessuna
dipendenza ORM: una tabella sola non giustifica SQLAlchemy, e per un
pannello a bassa concorrenza (un singolo admin) query parametrizzate dirette
restano più semplici da leggere e mantenere.
"""

import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone

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
                watched_at TEXT NOT NULL DEFAULT '',
                added_by TEXT NOT NULL DEFAULT '',
                proposed_by TEXT NOT NULL DEFAULT '',
                collection TEXT NOT NULL DEFAULT '',
                release_year TEXT NOT NULL DEFAULT '',
                runtime INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Migrazione per i database già esistenti (volume persistente sul
        # Raspberry): colonne aggiunte dopo la prima versione della tabella.
        cur.execute("PRAGMA table_info(movies)")
        existing_columns = {row["name"] for row in cur.fetchall()}
        for column in ("watched_at", "added_by", "proposed_by", "collection", "release_year"):
            if column not in existing_columns:
                cur.execute(f"ALTER TABLE movies ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        if "runtime" not in existing_columns:
            # Durata in minuti (0 = sconosciuta).
            cur.execute("ALTER TABLE movies ADD COLUMN runtime INTEGER NOT NULL DEFAULT 0")

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
        # Valori scelti da una select: corrispondenza esatta ("Prime" non deve
        # trovare anche "Prime Video").
        clause += " AND platform = ? COLLATE NOCASE"
        params.append(platform)
    # `genre` può contenere più generi separati da virgola ("Azione,Fantascienza"):
    # il film deve averli tutti. Anche il campo genere del film può averne
    # più d'uno: confronto sul singolo genere esatto.
    for single in (g.strip() for g in (genre or "").split(",")):
        if single:
            clause += " AND (',' || REPLACE(genre, ', ', ',') || ',') LIKE ? COLLATE NOCASE"
            params.append(f"%,{single},%")
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
    """Film più recenti per primi, ma i film della stessa saga (campo
    "collection") restano contigui: il gruppo prende la posizione del suo
    film inserito più di recente e, dentro il gruppo, l'ordine è per anno di
    uscita. Ogni riga porta anche quanti film ha la saga nel catalogo
    (collection_size) e quanti ne risultano visti (collection_seen)."""
    clause, params = _movies_where(status, platform, genre, search)
    offset = max(page - 1, 0) * page_size
    query = f"""
        SELECT movies.*,
            CASE WHEN collection = '' THEN 0 ELSE
                (SELECT COUNT(*) FROM movies m2 WHERE m2.collection = movies.collection COLLATE NOCASE)
            END AS collection_size,
            CASE WHEN collection = '' THEN 0 ELSE
                (SELECT COUNT(*) FROM movies m2
                 WHERE m2.collection = movies.collection COLLATE NOCASE AND m2.status = 'visto')
            END AS collection_seen
        FROM movies {clause}
        ORDER BY
            CASE WHEN collection = '' THEN created_at ELSE
                (SELECT MAX(m3.created_at) FROM movies m3 WHERE m3.collection = movies.collection COLLATE NOCASE)
            END DESC,
            LOWER(collection),
            release_year,
            created_at
        LIMIT ? OFFSET ?
    """

    with db_cursor() as cur:
        cur.execute(query, params + [page_size, offset])
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_movie(movie_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def _validate_watched_at(value) -> str:
    """Data di visione: stringa vuota oppure una data ISO valida (YYYY-MM-DD)."""
    value = (value or "").strip()
    if not value:
        return ""
    try:
        date.fromisoformat(value)
    except ValueError as e:
        raise ValueError("Data di visione non valida (formato atteso: AAAA-MM-GG).") from e
    return value


def _validate_year(value) -> str:
    """Anno di uscita: vuoto oppure 4 cifre."""
    value = str(value or "").strip()
    if value and not (len(value) == 4 and value.isdigit()):
        raise ValueError("Anno di uscita non valido (4 cifre, es. 2014).")
    return value


def _validate_runtime(value) -> int:
    """Durata in minuti: vuota/0 = sconosciuta, altrimenti 1-1000."""
    if value in (None, ""):
        return 0
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        raise ValueError("Durata non valida (minuti, es. 125).") from None
    if minutes < 0 or minutes > 1000:
        raise ValueError("Durata non valida (da 0 a 1000 minuti).")
    return minutes


def get_filter_options() -> dict:
    """Valori distinti di genere, piattaforma e proponente presenti nel
    catalogo, per le select dei filtri e i suggerimenti del form. I generi sono spezzati sulla virgola (un film può averne
    più di uno); i duplicati che differiscono solo per maiuscole si fondono."""

    def distinct(values) -> list[str]:
        seen: dict[str, str] = {}
        for value in values:
            value = value.strip()
            if value:
                seen.setdefault(value.casefold(), value)
        return sorted(seen.values(), key=str.casefold)

    with db_cursor() as cur:
        cur.execute("SELECT genre, platform, proposed_by, collection FROM movies")
        rows = cur.fetchall()

    genres = distinct(g for row in rows for g in row["genre"].split(","))
    platforms = distinct(row["platform"] for row in rows)
    proposers = distinct(row["proposed_by"] for row in rows)
    collections = distinct(row["collection"] for row in rows)
    return {"genres": genres, "platforms": platforms, "proposers": proposers, "collections": collections}


def create_movie(data: dict, added_by: str = "") -> dict:
    """added_by è l'utente del pannello che inserisce il film: arriva sempre
    dal token di sessione, mai dal corpo della richiesta (non falsificabile)."""
    now = _now()
    watched_at = _validate_watched_at(data.get("watched_at"))
    release_year = _validate_year(data.get("release_year"))
    runtime = _validate_runtime(data.get("runtime"))
    status = data.get("status") or "da_guardare"
    if status not in VALID_STATUSES:
        raise ValueError(f"Stato non valido: {status}")

    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO movies (title, link, platform, status, cover_url, genre, notes, watched_at, added_by, proposed_by, collection, release_year, runtime, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["title"].strip(),
                data.get("link", "").strip(),
                data.get("platform", "").strip(),
                status,
                data.get("cover_url", "").strip(),
                data.get("genre", "").strip(),
                data.get("notes", "").strip(),
                watched_at,
                added_by.strip(),
                (data.get("proposed_by") or "").strip(),
                (data.get("collection") or "").strip(),
                release_year,
                runtime,
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

    fields = ["title", "link", "platform", "status", "cover_url", "genre", "notes", "watched_at", "proposed_by", "collection", "release_year", "runtime"]
    updates = {f: data[f] for f in fields if f in data}
    if "watched_at" in updates:
        updates["watched_at"] = _validate_watched_at(updates["watched_at"])
    if "release_year" in updates:
        updates["release_year"] = _validate_year(updates["release_year"])
    if "runtime" in updates:
        updates["runtime"] = _validate_runtime(updates["runtime"])
    if "collection" in updates:
        updates["collection"] = (updates["collection"] or "").strip()
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


def movies_without_collection_info(after_id: int, limit: int) -> list[dict]:
    """Film da completare con i dati TMDB: né saga né anno di uscita, oppure
    durata sconosciuta. Servono al rilevamento automatico sui film inseriti
    prima di queste funzioni."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, title, collection, release_year, runtime FROM movies "
            "WHERE ((collection = '' AND release_year = '') OR runtime = 0) AND id > ? ORDER BY id LIMIT ?",
            (after_id, limit),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def _normalize_title(title: str) -> str:
    """Per confrontare titoli ignorando maiuscole, spazi e punteggiatura."""
    return re.sub(r"[\W_]+", "", (title or "").casefold())


def find_duplicates(title: str, release_year: str = "", exclude_id: int | None = None) -> list[dict]:
    """Film già presenti con lo stesso titolo. Se entrambi hanno l'anno di
    uscita, devono coincidere (due film omonimi di anni diversi non sono
    duplicati); se manca da una parte, il solo titolo basta per segnalare."""
    wanted = _normalize_title(title)
    if not wanted:
        return []
    year = (release_year or "").strip()

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, title, release_year, status, platform, added_by, proposed_by, created_at FROM movies"
        )
        rows = cur.fetchall()

    return [
        _row_to_dict(row)
        for row in rows
        if row["id"] != exclude_id
        and _normalize_title(row["title"]) == wanted
        and (not year or not row["release_year"] or row["release_year"] == year)
    ]


def get_stats() -> dict:
    """Conteggio film visti / da guardare, totale e per genere. Un film con
    più generi conta in ciascuno di essi."""
    with db_cursor() as cur:
        cur.execute("SELECT status, genre, runtime FROM movies")
        rows = cur.fetchall()

    seen = sum(1 for row in rows if row["status"] == "visto")
    by_genre: dict[str, dict] = {}
    for row in rows:
        genres = [g.strip() for g in row["genre"].split(",") if g.strip()] or ["Senza genere"]
        for genre in genres:
            entry = by_genre.setdefault(genre.casefold(), {"genre": genre, "seen": 0, "unseen": 0})
            entry["seen" if row["status"] == "visto" else "unseen"] += 1

    # Tempo di visione in minuti: i film senza durata nota non sono sommati,
    # ma contati a parte per non far credere che il totale sia completo.
    seen_rows = [row for row in rows if row["status"] == "visto"]
    unseen_rows = [row for row in rows if row["status"] != "visto"]
    runtime = {
        "seen_minutes": sum(row["runtime"] for row in seen_rows),
        "unseen_minutes": sum(row["runtime"] for row in unseen_rows),
        "seen_without_runtime": sum(1 for row in seen_rows if not row["runtime"]),
        "unseen_without_runtime": sum(1 for row in unseen_rows if not row["runtime"]),
    }

    genres_list = [{**e, "total": e["seen"] + e["unseen"]} for e in by_genre.values()]
    genres_list.sort(key=lambda e: (-e["total"], e["genre"].casefold()))
    return {"total": len(rows), "seen": seen, "unseen": len(rows) - seen, "by_genre": genres_list, **runtime}
