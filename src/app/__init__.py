from flask import Flask
from flask_migrate import upgrade

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
from .services.age_initializer import initialize_age_database


def create_app() -> Flask:
    import os
    
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    
    # Initialize Flask-Migrate with the correct migrations directory
    migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
    migrate.init_app(app, db, directory=migrations_dir)

    app.register_blueprint(health.bp)
    app.register_blueprint(main.bp)

    # Run database initialization automatically on startup
    with app.app_context():
        try:
            # Step 1: Create all tables if they don't exist (for initial setup)
            db.create_all()
            app.logger.info("Database tables created/verified")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}")
            # Continue anyway - migrations might handle it

        try:
            # Step 2: Run Flask-Migrate migrations
            upgrade()
            app.logger.info("Database migrations applied successfully")
        except Exception as e:
            app.logger.error(f"Error applying database migrations: {e}")
            # Optionally, you can choose to raise the exception to prevent app startup
            # Uncomment to make it fatal: raise

        try:
            # Step 3: Initialize Apache AGE extension and genealogy graph
            if initialize_age_database(db):
                app.logger.info("AGE database initialized successfully")
            else:
                app.logger.warning("AGE database initialization completed with warnings")
        except Exception as e:
            app.logger.error(f"Error initializing AGE database: {e}")
            # AGE initialization failure is non-fatal - app can still run without graph features
            # Uncomment to make it fatal: raise

    return app
