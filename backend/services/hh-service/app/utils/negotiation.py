from typing import Optional

from app.clients.hh.simple_hh_client import SimpleHHClient
from app.clients.db_client import APICLient
from app.utils.resume_parsing import parse_hh_resume_to_candidate
from app.utils.candidate_lookup import find_existing_candidate_id
from app.app_logging import logger
from app import config


async def process_negotiation(payload: dict, hh: SimpleHHClient, db: APICLient):
    try:
        if payload.get("action_type") != "NEW_NEGOTIATION_VACANCY":
            return

        event = payload.get("payload", {})
        hh_vacancy_id = str(event.get("vacancy_id"))
        resume_id = event.get("resume_id")
        chat_id = event.get("chat_id")

        if not hh_vacancy_id or not resume_id:
            logger.warning("Missing vacancy_id or resume_id")
            return

        # 1. Проверка вакансии в БД
        local_vacancy = await db.get(f"/vacancy/hh/{hh_vacancy_id}")
        if not local_vacancy:
            logger.info(f"Vacancy {hh_vacancy_id} not found — skipping")
            return

        # 2. Получение резюме
        resume = await hh._request("GET", f"/resumes/{resume_id}")
        if not resume:
            logger.warning(f"Empty resume response for {resume_id} — skipping")
            return
        logger.info(f"Got resume id={resume_id}, title={resume.get('title')}")

        # 3. Парсинг
        candidate_data = parse_hh_resume_to_candidate(resume)
        payload = candidate_data.model_dump(mode="json")
        existing_id = await find_existing_candidate_id(
            db,
            resume_id=str(resume_id),
            phone=payload.get("phone_number"),
            email=payload.get("email"),
        )
        if existing_id:
            logger.info(
                "Negotiation for resume %s skipped — candidate %s already exists",
                resume_id,
                existing_id,
            )
            return

        # 4. Создание кандидата
        candidate_resp = await db.post(
            "/candidate", json=payload
        )
        if not candidate_resp:
            logger.warning("Failed to create candidate — skipping")
            return
        candidate_id = candidate_resp["id"]

        # 5. Связь с вакансией
        await db.post(
            "/candidate/vacancy",
            json={
                "candidate_id": candidate_id,
                "vacancy_id": local_vacancy["id"],
                "status": "откликнулся",
                "is_active": True,
            },
        )

        # 6. Генерация invite_url
        invite_url = f"https://t.me/{config.BOT_NAME}"
        try:
            invite_resp = await db.post("/invite_url", json={"role": "candidate", "id": candidate_id})
            if not invite_resp:
                logger.warning("Empty invite_url response")
            else:
                invite_url = invite_resp.get("url") or invite_url
        except Exception as e:
            logger.error(f"Failed to get invite_url: {e}")

        # 7. Отправка сообщения
        try:
            message_text = config.invite_message(resume['first_name'], invite_url)
            nid = await get_negotiation_id_in_response_collection(hh, hh_vacancy_id, chat_id)
            if nid:
                await hh._request(
                    "POST",
                    f"/negotiations/{nid}/messages",
                    data={"message": message_text}
                )
                logger.info(f"Sent message via negotiation {nid}")
            else:
                logger.warning(f"negotiation_id not found in 'response' for chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    except Exception as e:
        logger.exception(f"Unexpected error in background negotiation handler: {e}")


async def get_negotiation_id_in_response_collection(
    hh: SimpleHHClient,
    vacancy_id: str,
    chat_id: str,
    per_page: int = 50,
    max_pages: int = 5  # response редко содержит >250 откликов
) -> Optional[str]:
    """
    Ищет negotiation_id по chat_id только в коллекции 'response' (неразобранные отклики).
    """
    try:
        # 1. Получаем метаданные коллекций
        negotiations_meta = await hh._request("GET", "/negotiations", params={"vacancy_id": vacancy_id})
        collections = negotiations_meta.get("collections", [])

        # 2. Находим URL коллекции "response"
        response_collection = next((c for c in collections if c["id"] == "response"), None)
        if not response_collection:
            logger.warning(f"'response' collection not found for vacancy {vacancy_id}")
            return None

        collection_url = response_collection["url"].split("https://api.hh.ru")[1]

        # 3. Перебираем страницы коллекции "response"
        for page in range(max_pages):
            try:
                page_data = await hh._request(
                    "GET",
                    collection_url,
                    params={"page": page, "per_page": per_page}
                )
            except Exception as e:
                logger.warning(f"Failed to fetch 'response' collection page {page}: {e}")
                break

            items = page_data.get("items", [])
            if not items:
                break

            # 4. Ищем нужный chat_id
            for item in items:
                if str(item.get("chat_id")) == str(chat_id):
                    return item["id"]

            # Если меньше per_page — это последняя страница
            if len(items) < per_page:
                break

    except Exception as e:
        logger.error(f"Error searching in 'response' collection for chat_id {chat_id}: {e}")

    return None

