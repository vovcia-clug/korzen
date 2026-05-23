from flask import Blueprint, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health_check():
    return jsonify({"status": "ok"})


@bp.get("/status")
def status_check():
    db_status = "unknown"
    age_installed = False
    detail = {}

    try:
        db.session.execute(text("SELECT 1"))
        db_status = "ok"

        age_result = db.session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'age'")
        )
        age_installed = age_result.scalar() is not None
    except Exception as exc:
        db_status = "error"
        detail["error"] = str(exc)

    detail["db"] = db_status
    detail["age_extension_installed"] = age_installed

    status = "ok" if db_status == "ok" and age_installed else "error"

    return jsonify({"status": status, "detail": detail})
