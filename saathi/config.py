import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-not-for-prod")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "saathi.db"))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    TICK_TOKEN = os.environ.get("TICK_TOKEN", "")
    TICK_SECONDS = int(os.environ.get("TICK_SECONDS", "30"))
    APP_URL = os.environ.get("APP_URL", "").rstrip("/")
    MAIL_ENABLED = os.environ.get("MAIL_ENABLED", "").lower() in {"1", "true", "yes"}
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "465"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "Saathi <noreply@localhost>")
    MAIL_TIMEOUT = float(os.environ.get("MAIL_TIMEOUT", "10"))
    LATE_THRESHOLD = timedelta(minutes=10)
    MISFIRE_GRACE = timedelta(hours=24)
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
    RATELIMIT_ENABLED = False


MAP = {
    "dev": DevelopmentConfig,
    "prod": ProductionConfig,
    "test": TestingConfig,
}
