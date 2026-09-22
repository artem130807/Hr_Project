from types import SimpleNamespace

from app.calls.phones import (
    call_involves_allowed_phones,
    canonical_ru_phone,
    conversation_involves_allowed_phones,
    parse_phone_allowlist,
)


def test_both_hr_spellings_are_the_same_mobile():
    assert canonical_ru_phone("+7 902 001 37 28") == "79020013728"
    assert canonical_ru_phone("+7 902 001 3728") == "79020013728"
    allowed = parse_phone_allowlist("+7 902 001 37 28,+7 902 001 3728")
    assert allowed == frozenset({"79020013728"})


def test_involves_caller_or_operator_with_formatting():
    allowed = parse_phone_allowlist("+7 902 001 37 28,+7 902 001 3728")
    assert call_involves_allowed_phones("+7 902 001 37 28", "+79000000000", allowed)
    assert call_involves_allowed_phones("8 (903) 551-77-02", "89020013728", allowed)
    assert not call_involves_allowed_phones("+79992140831", "+79007654321", allowed)
    assert conversation_involves_allowed_phones(
        SimpleNamespace(caller_number="+79035517702", operator_number="+7 902 001 3728"),
        allowed,
    )
    assert not conversation_involves_allowed_phones(
        SimpleNamespace(caller_number="+79992140831", operator_number="+79000000000"),
        allowed,
    )


def test_star_allowlist_disables_filter():
    assert parse_phone_allowlist("*") == frozenset()
    assert call_involves_allowed_phones("+7999", "+7900", frozenset())
