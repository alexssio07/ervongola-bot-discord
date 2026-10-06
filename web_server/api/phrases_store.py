"""
Lettura/scrittura in-place dei file JSON di frasi usati dal bot
(frasiaddio.json, frasieffetto.json, blasfemia.json), nella cartella
condivisa json/ alla root del repo (vedi config.BOT_JSON_DIR).

Sostituisce la logica del vecchio api/app.py, che aveva alcuni bug reali:
  - `jsonify({data})` in get_file: {data} è un set-literal su un dict, che
    solleva TypeError ("unhashable type: dict") ad ogni chiamata — la GET
    non ha mai funzionato.
  - `if not isinstance(items["frasi"], list) or "frasi" not in items["frasi"]`
    in save_file: la seconda condizione controlla se la stringa "frasi" è
    un ELEMENTO della lista items["frasi"] (non ha senso — controllava
    l'array su se stesso invece che il payload contenitore), quindi la
    validazione non validava nulla di utile.
  - gestiva solo "blasfemia" e "frasieffetto": "frasiaddio" non era previsto.
  - endpoint (/api/getFile/<f>, /api/saveFile/<f>) diversi da quelli che il
    frontend (ConfigEditorList.tsx) chiamava davvero (/api/<f>): la UI non
    poteva funzionare contro questo backend.

Ogni file ha un formato leggermente diverso:
  - frasiaddio.json:   {"frasi": ["stringa", "stringa", ...]}
  - frasieffetto.json: {"frasi": [{"text": "...", "users": [...]}, ...]}
  - blasfemia.json:    {"bestemmie": [{"text": "..."}, ...]}

FILE_REGISTRY astrae queste differenze così backend e frontend trattano i
tre file allo stesso identico modo (index, text).
"""

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from config import BOT_JSON_DIR


@dataclass(frozen=True)
class FileSpec:
    filename: str
    list_key: str
    # Se True, ogni elemento della lista è un oggetto {"text": ..., ...};
    # se False, è una stringa semplice (caso di frasiaddio.json).
    is_object: bool
    label: str
    # Campi extra da aggiungere quando si crea un NUOVO elemento oggetto,
    # per rispettare lo schema che il bot si aspetta in quel file
    # (frasieffetto.json tiene traccia di "users" per ogni frase,
    # blasfemia.json invece no).
    new_item_extra: dict = field(default_factory=dict)


FILE_REGISTRY: dict[str, FileSpec] = {
    "frasiaddio": FileSpec("frasiaddio.json", "frasi", is_object=False, label="Frasi d'addio"),
    "frasieffetto": FileSpec(
        "frasieffetto.json",
        "frasi",
        is_object=True,
        label="Frasi d'effetto (ingresso canale)",
        new_item_extra={"users": []},
    ),
    "blasfemia": FileSpec("blasfemia.json", "bestemmie", is_object=True, label="Blasfemie"),
}

# Un lock per file: evita che due richieste concorrenti sul pannello si
# pestino i piedi durante un read-modify-write. Non protegge da scritture
# concorrenti del processo del BOT (separato) sullo stesso file — per quello
# resta "ultimo che scrive vince", accettabile per un pannello a basso
# volume di modifiche (stesso compromesso già accettato da utils.py/bot per
# le sue scritture atomiche).
_locks: dict[str, threading.Lock] = {key: threading.Lock() for key in FILE_REGISTRY}


class PhraseFileError(Exception):
    pass


def _spec(file_key: str) -> FileSpec:
    spec = FILE_REGISTRY.get(file_key)
    if spec is None:
        raise PhraseFileError(f"File sconosciuto: {file_key}")
    return spec


def _path(spec: FileSpec) -> Path:
    return BOT_JSON_DIR / spec.filename


def _load_raw(spec: FileSpec) -> dict:
    path = _path(spec)
    if not path.exists():
        return {spec.list_key: []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise PhraseFileError(f"JSON non valido in {path.name}: {e}") from e
    data.setdefault(spec.list_key, [])
    return data


def _save_raw(spec: FileSpec, data: dict) -> None:
    """Scrittura atomica: file temporaneo + rename, come già fa utils.py nel bot."""
    path = _path(spec)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    tmp_path.replace(path)


def _extract_text(spec: FileSpec, item) -> str:
    if spec.is_object:
        return str(item.get("text", ""))
    return str(item)


def list_files() -> list[dict]:
    return [{"key": key, "label": spec.label} for key, spec in FILE_REGISTRY.items()]


def get_page(file_key: str, search: str | None, page: int, page_size: int) -> dict:
    spec = _spec(file_key)
    data = _load_raw(spec)
    items = data[spec.list_key]

    indexed = [{"index": i, "text": _extract_text(spec, item)} for i, item in enumerate(items)]

    if search and search.strip():
        # "cerca ogni parola": ogni parola della query deve comparire nel
        # testo (AND fra i termini), case-insensitive.
        words = [w.lower() for w in search.strip().split() if w]
        indexed = [row for row in indexed if all(w in row["text"].lower() for w in words)]

    total = len(indexed)
    start = max(page - 1, 0) * page_size
    page_items = indexed[start : start + page_size]

    return {
        "file_key": file_key,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_items,
    }


def add_phrase(file_key: str, text: str) -> int:
    spec = _spec(file_key)
    text = text.strip()
    if not text:
        raise PhraseFileError("Il testo della frase non può essere vuoto.")

    with _locks[file_key]:
        data = _load_raw(spec)
        items = data[spec.list_key]

        if any(_extract_text(spec, item).lower() == text.lower() for item in items):
            raise PhraseFileError("Questa frase esiste già.")

        new_item = {"text": text, **spec.new_item_extra} if spec.is_object else text
        items.append(new_item)
        _save_raw(spec, data)
        return len(items) - 1


def update_phrase(file_key: str, index: int, text: str) -> None:
    spec = _spec(file_key)
    text = text.strip()
    if not text:
        raise PhraseFileError("Il testo della frase non può essere vuoto.")

    with _locks[file_key]:
        data = _load_raw(spec)
        items = data[spec.list_key]

        if index < 0 or index >= len(items):
            raise PhraseFileError("Indice frase non valido (la lista potrebbe essere cambiata).")

        if spec.is_object:
            items[index]["text"] = text
        else:
            items[index] = text

        _save_raw(spec, data)


def delete_phrase(file_key: str, index: int) -> None:
    spec = _spec(file_key)

    with _locks[file_key]:
        data = _load_raw(spec)
        items = data[spec.list_key]

        if index < 0 or index >= len(items):
            raise PhraseFileError("Indice frase non valido (la lista potrebbe essere cambiata).")

        items.pop(index)
        _save_raw(spec, data)
