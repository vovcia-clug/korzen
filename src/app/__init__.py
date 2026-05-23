from flask import Flask, request, session
from flask_babel import Babel
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
from .langfuse_config import init_langfuse


def initialize_pgvector_extension(app):
    """Initialize pgvector extension in the database."""
    try:
        with db.engine.connect() as conn:
            # Check if pgvector extension exists
            result = conn.execute(db.text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                );
            """))
            exists = result.scalar()
            
            if not exists:
                app.logger.info("Creating pgvector extension...")
                conn.execute(db.text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                app.logger.info("✓ pgvector extension created successfully")
            else:
                app.logger.info("✓ pgvector extension already exists")
                
            # Verify vector type is available
            result = conn.execute(db.text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'vector'
                );
            """))
            vector_exists = result.scalar()
            
            if vector_exists:
                app.logger.info("✓ Vector type is available")
                return True
            else:
                app.logger.error("✗ Vector type is not available after extension creation")
                return False
                
    except Exception as e:
        app.logger.error(f"Error initializing pgvector extension: {e}")
        app.logger.warning("pgvector features will not be available")
        return False


def get_locale():
    """Determine the best locale for the user."""
    from flask import has_request_context
    
    # Only access session/request if we're in a request context
    if not has_request_context():
        return 'pl'  # Default locale when called outside request context
    
    # 1. Check if user explicitly selected a language (stored in session)
    if 'language' in session:
        return session['language']
    
    # 2. Try to match browser's Accept-Language header
    return request.accept_languages.best_match(['pl', 'en']) or 'pl'


def get_timezone():
    """Get user's timezone (default: Europe/Warsaw for Polish users)."""
    return 'Europe/Warsaw'


def create_app() -> Flask:
    import os
    
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Langfuse tracing (must be done after config is loaded)
    init_langfuse(app)

    db.init_app(app)
    
    # Initialize Flask-Migrate with the correct migrations directory
    migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
    migrate.init_app(app, db, directory=migrations_dir)
    
    # Initialize Flask-Babel for internationalization
    babel = Babel(app, locale_selector=get_locale, timezone_selector=get_timezone)
    
    # Make get_locale available to all templates as a context processor
    @app.context_processor
    def inject_locale():
        """Inject get_locale function into all templates."""
        return dict(get_locale=get_locale)
    
    # Add Python built-in functions to Jinja2 environment
    app.jinja_env.globals.update({
        'min': min,
        'max': max,
    })
    
    # Log Babel initialization (get_locale now safely handles being called outside request context)
    app.logger.info(f"Flask-Babel initialized. Default locale: {get_locale()}")

    app.register_blueprint(health.bp)
    app.register_blueprint(main.bp)

    # Run database initialization automatically on startup
    with app.app_context():
        try:
            # Step 1: Initialize pgvector extension (must be done before migrations)
            initialize_pgvector_extension(app)
        except Exception as e:
            app.logger.error(f"Error initializing pgvector extension: {e}")
            # Continue anyway - app can work without vector features

        try:
            # Step 2: Run Flask-Migrate migrations (this creates/updates all tables)
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
