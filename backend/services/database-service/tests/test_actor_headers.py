from app.utils.actor import actor_from_headers


def test_actor_from_headers_unquotes_and_truncates():
    aid, aname = actor_from_headers(
        actor_id="x" * 50,
        actor_name="%D0%90%D0%BD%D0%BD%D0%B0",
    )
    assert aid == "x" * 36
    assert aname == "Анна"
