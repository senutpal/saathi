import pytest
from flask import abort

from saathi import create_app


def test_healthz_returns_ok_json(client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_home_redirects_anonymous_visitor_to_login(client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")
    assert "next=" in response.headers["Location"]


def test_style_gallery_hidden_outside_development(client) -> None:
    response = client.get("/dev/style")

    assert response.status_code == 404


def test_style_gallery_renders_components_in_development(app, client) -> None:
    app.config["SAATHI_ENV"] = "development"

    response = client.get("/dev/style")

    assert response.status_code == 200
    assert b"bg-primary" in response.data


def test_unknown_url_renders_custom_404(client) -> None:
    response = client.get("/definitely-missing")

    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_forbidden_renders_custom_403(app, client) -> None:
    @app.route("/denied")
    def denied():
        abort(403)

    response = client.get("/denied")

    assert response.status_code == 403
    assert b"403" in response.data


def test_internal_error_renders_custom_500(app, client) -> None:
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("boom")

    response = client.get("/boom")

    assert response.status_code == 500
    assert b"Something went wrong" in response.data


def test_factory_call_does_not_create_database_file(tmp_path) -> None:
    test_config = {
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE_PATH": str(tmp_path / "test.db"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SCHEDULER_ENABLED": False,
        "WTF_CSRF_ENABLED": False,
    }

    create_app(test_config=test_config)

    assert not (tmp_path / "test.db").exists()


def test_production_without_strong_secret_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("SAATHI_CONFIG", "prod")
    monkeypatch.setenv("SECRET_KEY", "short")

    with pytest.raises(RuntimeError):
        create_app()
