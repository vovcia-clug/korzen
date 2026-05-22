import os


class Config:
    # Flask secret key for session management
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@db:5432/korzen",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Babel Configuration
    BABEL_DEFAULT_LOCALE = 'pl'
    BABEL_SUPPORTED_LOCALES = ['pl', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
