from app.adaptation.links import public_adaptation_form_path, public_adaptation_form_url


def test_public_form_path_encodes_token():
    assert public_adaptation_form_path("token / one") == "/adaptation/forms/token%20%2F%20one"


def test_public_form_url_uses_hr_frontend_and_removes_api_suffix(monkeypatch):
    monkeypatch.setenv("HR_FRONTEND_BASE_URL", "https://hr.example.ru/v1/")
    monkeypatch.setenv("FRONTEND_URL", "https://wrong.example.ru")

    assert public_adaptation_form_url("abc") == "https://hr.example.ru/adaptation/forms/abc"


def test_public_form_url_falls_back_to_safe_relative_path(monkeypatch):
    monkeypatch.delenv("HR_FRONTEND_BASE_URL", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "not-a-url")

    assert public_adaptation_form_url("a/b") == "/adaptation/forms/a%2Fb"
