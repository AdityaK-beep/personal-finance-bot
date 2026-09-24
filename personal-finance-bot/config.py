import os
import secrets
import warnings
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Explicitly load .env from the project root directory
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)


class Config:
    """Base application configuration."""

    # Secret key handling: load from environment or generate a secure fallback for development
    _env_secret = os.environ.get('SECRET_KEY')
    if not _env_secret:
        warnings.warn(
            "SECURITY WARNING: SECRET_KEY is not set in environment or .env! "
            "A temporary random key is being generated for development. "
            "For production deployments, configure a persistent, secret key in .env or environment variables.",
            UserWarning
        )
        SECRET_KEY = secrets.token_hex(32)
    else:
        SECRET_KEY = _env_secret

    # Gemini API Key
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()

    # Database Configuration: absolute SQLite path based on project root
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'finance.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    """Testing configuration with in-memory database."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
