import pytest

from saathi import create_app
from saathi.extensions import db
from saathi.models import User


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
def make_user(session):
    def _make_user(
        email: str = "a@example.com", password: str = "correct horse", username: str = "a"
    ) -> User:
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    return _make_user


@pytest.fixture()
def login(client):
    def _login(email: str, password: str):
        return client.post("/auth/login", data={"email": email, "password": password})

    return _login


@pytest.fixture()
def logged_in_client(client, make_user, login):
    make_user()
    login("a@example.com", "correct horse")
    return client
