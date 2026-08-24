import pytest

from saathi import create_app
from saathi.extensions import db


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        test_config={
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE_PATH": str(tmp_path / "test.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SCHEDULER_ENABLED": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()
        for engine in db.engines.values():
            engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture()
def logged_in_client(app):
    raise NotImplementedError("real auth helper lands with P03")
