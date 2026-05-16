from flask import Flask

from .config import Config
from .extensions import db, migrate
from .models import (
    BaptismRecord,
    DeathRecord,
    GenealogicalRecord,
    GodparentRelationship,
    MarriageRecord,
    Person,
    RecordBatch,
    SocialStatus,
    UploadedFile,
    WitnessRelationship,
)
from .routes import health, main


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(health.bp)
    app.register_blueprint(main.bp)

    return app
