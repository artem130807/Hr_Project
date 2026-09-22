MAX_TELEGRAM_MESSAGE_LENGTH = 3500

def split_message(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    """
    Делит длинный текст на части, чтобы каждая влезала в лимит Telegram.
    Разбивает по строкам или пробелам, чтобы не рвать слова.
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    while len(text) > max_length:
        split_index = text.rfind('\n', 0, max_length)
        if split_index == -1:
            split_index = text.rfind(' ', 0, max_length)
        if split_index == -1:
            split_index = max_length
        parts.append(text[:split_index].strip())
        text = text[split_index:].strip()
    if text:
        parts.append(text)
    return parts