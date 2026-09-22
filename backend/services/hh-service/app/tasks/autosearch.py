import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.clients.db_client import APICLient
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.config import EMPLOYER_ID, HH_RESUME_VIEW_LIMIT, BOT_NAME, invite_message
from app.utils.resume_parsing import parse_hh_resume_to_candidate
from app.utils.candidate_lookup import find_existing_candidate_id
from app.utils.resume_to_str import parse_resume_for_llm
from app.app_logging import logger


async def evaluate_resume(
    resume_json: dict,
    vacancy_json: dict,
    ai_client: APICLient,
    db_client: APICLient,
    max_retries: int = 3
) -> Optional[float]:
    """
    Оценивает резюме через AI service.
    Возвращает score (0-100) или None в случае ошибки.
    """
    try:
        resume_str = parse_resume_for_llm(resume_json)
        vacancy_data = await db_client.post(f"/vacancy/{vacancy_json['id']}/summary")
        payload = {
            "resume_str": resume_str,
            "vacancy_str": vacancy_data['text']
        }
        
        for attempt in range(max_retries):
            try:
                response = await asyncio.wait_for(
                    ai_client.post('/resume/evaluate', json=payload),
                    timeout=30.0
                )
                if response and 'score' in response:
                    score = float(response['score'])
                    logger.info(f"Resume {resume_json.get('id', 'unknown')} evaluated with score: {score}")
                    return score
                else:
                    logger.warning(f"AI service returned invalid response: {response}")
                    return None
            except asyncio.TimeoutError:
                logger.warning(f"AI service timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # exponential backoff
            except Exception as e:
                logger.error(f"Error evaluating resume (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return None
    except Exception as e:
        logger.error(f"Failed to evaluate resume after {max_retries} attempts: {str(e)}")
        return None


async def collect_resumes_by_keywords(
    hh: SimpleHHClient,
    hh_vacancy_id: str,
    area_id: Optional[int],
    keywords: list[str],
    max_resumes: int = 300
) -> set[str]:
    """
    Собирает резюме по ключевым словам для вакансии.
    Возвращает set уникальных resume_id.
    """
    all_resume_ids = set()
    
    for keyword in keywords:
        if len(all_resume_ids) >= max_resumes:
            break
            
        page = 0
        while len(all_resume_ids) < max_resumes:
            params = {
                "vacancy_id": hh_vacancy_id,
                "text": keyword,
                "order_by": "relevance",
                "per_page": 50,
                "page": page,
                "area": area_id
            }
            
            try:
                resumes_response = await hh._request("GET", f"/resumes", params=params)
                if not resumes_response or not resumes_response.get("items"):
                    break
                
                for resume in resumes_response.get("items", []):
                    resume_id = resume.get('id')
                    if resume_id:
                        all_resume_ids.add(resume_id)
                
                # Проверяем, есть ли еще страницы
                pages = resumes_response.get("pages", 1)
                if page >= pages - 1:
                    break
                page += 1
                
                await asyncio.sleep(0.5)  # Небольшая задержка между запросами
            except Exception as e:
                logger.error(f"Error collecting resumes for keyword '{keyword}': {str(e)}")
                break
    
    logger.info(f"Collected {len(all_resume_ids)} unique resumes for vacancy {hh_vacancy_id}")
    return all_resume_ids


async def autosearch(
        db: APICLient,
        hh: SimpleHHClient,
        ai_client: Optional[APICLient] = None
):
    """
    Улучшенная функция автопоиска с оценкой через AI.
    """
    searches = await db.get('/autosearch/active')
    if not searches:
        logger.info("No active searches")
        return
    
    # Получаем AI client если не передан
    if ai_client is None:
        from app.dependencies import get_ai_client
        ai_client = await get_ai_client()

    for search in searches:
        vacancy = await db.get(f"/vacancy/{search['vacancy_id']}")
        if not vacancy:
            logger.warning(f"Vacancy {search['vacancy_id']} not found, skip this search")
            continue

        hh_vacancy_id = vacancy.get('hh_vacancy_id')
        if not hh_vacancy_id:
            logger.warning(f"Vacancy {search['vacancy_id']} doesn't have hh_vacancy_id, skip this search")
            continue
        hh_vacancy = await hh._request("GET", f"/vacancies/{hh_vacancy_id}")
        if not hh_vacancy:
            logger.warning(f"Vacancy with hh_vacancy_id {hh_vacancy_id} not found on HH, skip this search")
            continue    
        expires_raw = hh_vacancy.get('expires_at')
        expires_at = None
        if expires_raw:
            try:
                expires_at = datetime.strptime(expires_raw, "%Y-%m-%dT%H:%M:%S%z")
            except (TypeError, ValueError):
                logger.warning(
                    f"Vacancy {search['vacancy_id']} has invalid expires_at={expires_raw!r}, ignore expiry check"
                )
        now = datetime.now(timezone.utc)
        if hh_vacancy.get('hidden') or hh_vacancy.get('archived') or (expires_at is not None and expires_at < now):
            logger.info(f"Vacancy {search['vacancy_id']} (hh_id: {hh_vacancy_id}) is not active, skip this search")
            await db.post(f"/autosearch/{search['id']}/deactivate")
            continue

        invite_limit = search.get('invite_limit', 10)
        vacancy_name = vacancy.get('name', '')
        synonyms = (vacancy.get('synonyms') or [])[:10]  # Ограничиваем до 10 synonyms
        
        # Формируем список ключевых слов для поиска
        keywords = [vacancy_name]
        if synonyms:
            keywords.extend(synonyms)
        
        logger.info(f"Starting autosearch for vacancy {search['vacancy_id']} (hh_id: {hh_vacancy_id}), keywords: {keywords}")
        
        # Шаг 1: Собираем резюме по ключевым словам
        resume_ids = await collect_resumes_by_keywords(hh, str(hh_vacancy_id), vacancy['area_id'], keywords)
        if not resume_ids:
            logger.info(f"No resumes found for vacancy {search['vacancy_id']}")
            continue
        
        # Шаг 2: Фильтруем уже обработанные резюме и оцениваем новые
        evaluated_count = 0
        for resume_id in resume_ids:
            # Проверяем, не обработано ли уже это резюме
            exists_result = await db.get('/reviewed-resumes/exists', params={"resume_id": resume_id})
            if exists_result and exists_result.get('exists'):
                continue
            
            try:
                # Получаем полные данные резюме
                resume_json = await hh._request("GET", f"/resumes/{resume_id}")
                if not resume_json:
                    logger.warning(f"Could not get resume data for {resume_id}")
                    continue
                
                # Оцениваем резюме через AI
                score = await evaluate_resume(resume_json, vacancy, ai_client, db)
                
                # Сохраняем в reviewed_resumes
                # Используем значения из enum EvaluationStatus и ResumeSearchStatus
                evaluation_status = 'evaluated' if score is not None else 'failed'
                status = 'pending'  # Статус pending означает что резюме найдено, но приглашение еще не отправлено
                
                await db.post('/reviewed-resumes', json={
                    "auto_search_id": search['id'],
                    "resume_id": resume_id,
                    "status": status,
                    "score": score,
                    "evaluation_status": evaluation_status
                })
                
                if score is not None:
                    evaluated_count += 1
                
                await asyncio.sleep(0.5)  # Задержка между запросами
            except Exception as e:
                logger.error(f"Error processing resume {resume_id}: {str(e)}")
                # Сохраняем с ошибкой
                try:
                    await db.post('/reviewed-resumes', json={
                        "auto_search_id": search['id'],
                        "resume_id": resume_id,
                        "status": "pending",
                        "evaluation_status": "failed"
                    })
                except:
                    pass
                continue
        
        logger.info(f"Evaluated {evaluated_count} resumes for vacancy {search['vacancy_id']}")
        
        # Шаг 3: Получаем лучшие резюме и отправляем приглашения
        best_resumes = await db.get(
            '/reviewed-resumes/best',
            params={"auto_search_id": search['id'], "limit": invite_limit*2}  # Берем с запасом на случай недоставки
        )
        
        if not best_resumes:
            logger.info(f"No evaluated resumes found for vacancy {search['vacancy_id']}")
            continue
        
        sent_count = 0
        i = 0
        while sent_count < invite_limit and i < len(best_resumes):
            reviewed_resume = best_resumes[i]
            i += 1
            resume_id = reviewed_resume['resume_id']
            try:
                # Получаем полные данные резюме для отправки приглашения
                resume_json = await hh._request("GET", f"/resumes/{resume_id}")
                if not resume_json:
                    continue
                
                invite_url = await process_candidate(resume_json, vacancy['id'], db)
                message = invite_message(resume_json.get('first_name', None), invite_url)
                
                await send_invite(resume_id, hh_vacancy_id, message, hh)
                
                # Обновляем статус на 'invited'
                await db.patch(
                    f"/reviewed-resumes/{reviewed_resume['id']}",
                    json={"status": "invited"}
                )
                
                sent_count += 1
                await db.post(f"/autosearch/{search['id']}/sent/add")
                logger.info(f"Invite sent to resume_id: {resume_id}, vacancy_id: {hh_vacancy_id}, score: {reviewed_resume.get('score')}")
                await asyncio.sleep(2)  # Задержка между отправками приглашений
            except Exception as e:
                logger.error(f"Error sending invite to resume_id: {resume_id}: {str(e)}")
                # Обновляем статус на 'unreachable'
                try:
                    await db.patch(
                        f"/reviewed-resumes/{reviewed_resume['id']}",
                        json={"status": "unreachable"}
                    )
                except:
                    pass
                continue
        
        logger.info(f"Sent {sent_count} invites for vacancy {search['vacancy_id']}")
        
    return True


async def send_invite(
        resume_id: str, 
        vacancy_id: int, 
        message: str,
        hh: SimpleHHClient,
    ):
    """
    Send message to chat by vacancy and resume IDS
    """
    vacancy_params = {
                    'resume_id': resume_id
    }

    vacancy_list = await hh._request(
        "GET",
        f'/employers/{EMPLOYER_ID}/vacancies/active',
        params={**vacancy_params, "all_accessible": "true"},
    )
    if not vacancy_list:
        raise Exception("HH vacancies isn't available failed")
    vacancy_items = vacancy_list.get('items', {})
    current_vacancy = next((vacancy for vacancy in vacancy_items if vacancy.get('id') == str(vacancy_id)), None)
    if current_vacancy is None:
        raise Exception("Vacancy not found")

    actions = current_vacancy.get('negotiations_actions')
    if not actions:
        raise Exception("No negotiation actions")

    phone_interview = next(
        (action for action in actions if action.get("id") == "phone_interview"),
        None
)

    if phone_interview is None:
        raise Exception("phone_interview action not available")

    payload = {
        "resume_id": resume_id,  
        "vacancy_id": vacancy_id,                       
        "message": message
    }
    response = await hh._request("POST", phone_interview['url'], params=payload)
    if not response:
        raise Exception()
    
    
async def process_candidate(
        resume_json: dict,
        local_vacancy_id: int,
        db: APICLient,
):
    """
    Creating candidate in database, connecting to vacancy and generating invite_url
    """
    # 3. Парсинг
    candidate_data = parse_hh_resume_to_candidate(resume_json)
    payload = candidate_data.model_dump(mode="json")
    existing_id = await find_existing_candidate_id(
        db,
        resume_id=resume_json.get("id") or payload.get("hh_resume_link"),
        phone=payload.get("phone_number"),
        email=payload.get("email"),
    )
    if existing_id:
        logger.info("Autosearch skipped duplicate candidate %s", existing_id)
        return existing_id

    # 4. Создание кандидата
    candidate_resp = await db.post(
        "/candidate", json=payload
    )
    if not candidate_resp:
        logger.warning("Failed to create candidate — skipping")
        return None
    candidate_id = candidate_resp["id"]

    # 5. Связь с вакансией
    await db.post(
        "/candidate/vacancy",
        json={
            "candidate_id": candidate_id,
            "vacancy_id": local_vacancy_id,
            "status": "холодный контакт",
            "is_active": True,
        },
    )

    # 6. Генерация invite_url
    invite_url = f"https://t.me/{BOT_NAME}"
    try:
        invite_resp = await db.post("/invite_url", json={"role": "candidate", "id": candidate_id})
        if not invite_resp:
            logger.warning("Empty invite_url response")
        else:
            invite_url = invite_resp.get("url") or invite_url
    except Exception as e:
            logger.error(f"Failed to get invite_url: {e}")
    
    return invite_url