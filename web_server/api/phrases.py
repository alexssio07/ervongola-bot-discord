from flask import Blueprint, jsonify, request

import phrases_store as store
from auth import require_auth

bp = Blueprint("phrases", __name__, url_prefix="/api/phrases")


@bp.get("/files")
@require_auth
def get_files():
    """Elenco dei file JSON gestibili, per popolare i tab del menu 'Modifica frasi'."""
    return jsonify(store.list_files())


@bp.get("/<file_key>")
@require_auth
def get_phrases(file_key: str):
    search = request.args.get("search")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 10)), 1), 200)

    try:
        result = store.get_page(file_key, search, page, page_size)
    except store.PhraseFileError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)


@bp.post("/<file_key>")
@require_auth
def add_phrase(file_key: str):
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")

    try:
        new_index = store.add_phrase(file_key, text)
    except store.PhraseFileError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"index": new_index}), 201


@bp.put("/<file_key>/<int:index>")
@require_auth
def update_phrase(file_key: str, index: int):
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")

    try:
        store.update_phrase(file_key, index, text)
    except store.PhraseFileError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})


@bp.delete("/<file_key>/<int:index>")
@require_auth
def delete_phrase(file_key: str, index: int):
    try:
        store.delete_phrase(file_key, index)
    except store.PhraseFileError as e:
        return jsonify({"error": str(e)}), 400

    return "", 204
