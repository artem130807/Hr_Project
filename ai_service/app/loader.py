from app.client.db_client import APICLient
from app.utils.auth_token_manager import TokenManager
from app.agent.v1.ai_client import AIClient
from app.agent.v1.services.vacancy_service import VacancyAIService
from app.agent.v1.services.candidate_service import CandidateAIService
from app.agent.v1.services.test_service import TestAIService
from app.config import CLIENT_ID, CLIENT_SECRET, DB_SERVICE_BASE_URL, OPENAI_API_TOKEN

token_manager = TokenManager(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_url=f"{DB_SERVICE_BASE_URL}/token/service")

db = APICLient(
    base_url=DB_SERVICE_BASE_URL,
    token_manager=token_manager,
    timeout=60.0,
    headers_required=True
)

ai_client = AIClient(
    api_key=OPENAI_API_TOKEN,
    model='gpt-4o-mini'
)

vacancy_service = VacancyAIService(
    ai_client=ai_client
)

candidate_service = CandidateAIService(
    ai_client=ai_client
)

test_service = TestAIService(
    ai_client=ai_client
)