import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-not-for-prod")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "saathi.db"))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    TICK_TOKEN = os.environ.get("TICK_TOKEN", "")
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    TIMEZONE = os.environ.get("TZ", "Asia/Kolkata")
    SAATHI_ENV = os.environ.get("FLASK_ENV", "development")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_NAME = "_saathi_session"


class DevelopmentConfig(Config):
    pass


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    SAATHI_ENV = "production"


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    SAATHI_ENV = "testing"
    SCHEDULER_ENABLED = False
    WTF_CSRF_ENABLED = False


MAP = {
    "dev": DevelopmentConfig,
    "prod": ProductionConfig,
    "test": TestingConfig,
}
