from app.mock import resume_example
from app.utils.resume_parsing import (
    extract_hh_resume_contacts,
    normalize_telegram_username,
    parse_hh_resume_to_candidate,
)


def test_normalize_telegram_username():
    assert normalize_telegram_username("@nickname") == "@nickname"
    assert normalize_telegram_username("nickname") == "@nickname"
    assert normalize_telegram_username("https://t.me/nickname") == "@nickname"
    assert normalize_telegram_username("t.me/nickname") == "@nickname"
    assert normalize_telegram_username("") is None
    assert normalize_telegram_username("too many words") is None


def test_extract_contacts_from_hh_mock():
    contacts = extract_hh_resume_contacts(resume_example["contact"])
    assert contacts.phone == "+74955527367"
    assert contacts.telegram == "@nickname"
    assert contacts.email == "my-email@example.com"


def test_parse_hh_resume_includes_contacts():
    candidate = parse_hh_resume_to_candidate(resume_example)
    assert candidate.telegram_username == "@nickname"
    assert candidate.email == "my-email@example.com"
    assert candidate.phone_number
    assert candidate.full_name == "Иванов Иван"


def test_format_hh_full_name_is_fio_order():
    from app.utils.resume_parsing import format_hh_full_name

    assert format_hh_full_name(
        last_name="Сергеев",
        first_name="Артём",
        middle_name="Валерьевич",
    ) == "Сергеев Артём Валерьевич"
    assert format_hh_full_name(
        resume={"first_name": "Иван", "last_name": "Иванов", "middle_name": "Иванович"}
    ) == "Иванов Иван Иванович"


def test_extract_telegram_from_nested_value():
    contacts = extract_hh_resume_contacts(
        [
            {
                "type": {"id": "cell", "name": "Мобильный телефон"},
                "value": {"formatted": "+7 (925) 111-22-33"},
            },
            {
                "type": {"id": "telegram", "name": "Telegram"},
                "value": {"username": "from_resume"},
            },
            {
                "type": {"id": "email", "name": "Эл. почта"},
                "value": "User@Mail.RU",
            },
        ]
    )
    assert contacts.phone == "+79251112233"
    assert contacts.telegram == "@from_resume"
    assert contacts.email == "user@mail.ru"


def test_extract_telegram_from_site_block():
    contacts = extract_hh_resume_contacts(
        {
            "contact": [
                {"type": {"id": "email", "name": "Эл. почта"}, "value": "a@b.com"},
            ],
            "site": [
                {"type": {"id": "telegram", "name": "Telegram"}, "url": "https://t.me/site_user"},
                {"type": {"id": "skype", "name": "Skype"}, "url": "live:someone"},
            ],
        }
    )
    assert contacts.email == "a@b.com"
    assert contacts.telegram == "@site_user"
