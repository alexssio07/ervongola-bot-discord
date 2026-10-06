"""Blueprint CRUD per il catalogo film, con filtri per tag/piattaforma/genere/ricerca."""

from flask import Blueprint, jsonify, request

import db
from auth import require_auth

bp = Blueprint("movies", __name__, url_prefix="/api/movies")

REQUIRED_FIELDS = ("title",)


@bp.get("")
@require_auth
def list_movies():
    status = request.args.get("status") or None
    platform = request.args.get("platform") or None
    genre = request.args.get("genre") or None
    search = request.args.get("search") or None
    page = max(int(request.args.get("page", 1)), 1)
    # Stesso tetto massimo già usato per le frasi (200), per non permettere
    # a un client di chiedere l'intero catalogo in una volta sola.
    page_size = min(max(int(request.args.get("page_size", 12)), 1), 200)

    total = db.count_movies(status, platform, genre, search)
    movies = db.list_movies(status, platform, genre, search, page=page, page_size=page_size)

    return jsonify({"items": movies, "total": total, "page": page, "page_size": page_size})


@bp.get("/<int:movie_id>")
@require_auth
def get_movie(movie_id: int):
    movie = db.get_movie(movie_id)
    if movie is None:
        return jsonify({"error": "Film non trovato."}), 404
    return jsonify(movie)


@bp.post("")
@require_auth
def create_movie():
    payload = request.get_json(silent=True) or {}
    missing = [f for f in REQUIRED_FIELDS if not payload.get(f, "").strip()]
    if missing:
        return jsonify({"error": f"Campi obbligatori mancanti: {', '.join(missing)}"}), 400

    try:
        movie = db.create_movie(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(movie), 201


@bp.put("/<int:movie_id>")
@require_auth
def update_movie(movie_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        movie = db.update_movie(movie_id, payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if movie is None:
        return jsonify({"error": "Film non trovato."}), 404
    return jsonify(movie)


@bp.delete("/<int:movie_id>")
@require_auth
def delete_movie(movie_id: int):
    deleted = db.delete_movie(movie_id)
    if not deleted:
        return jsonify({"error": "Film non trovato."}), 404
    return "", 204
