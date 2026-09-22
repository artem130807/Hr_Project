from aiogram.types import Message

from app.api.redis_client import RedisClient
from app.api.db_client import APIClient
from app.api.endpoints import Endpoints
from app.api.enums import TestType, TestResultsType
from app.config import EXTERNAL_RPOCESSED_TEST_PASSED_COMMAND, TEST_WITH_QUESTIONS_EXTRA_INFO
from app.app_logging import logger


class Question:
    def __init__(self, 
                 text: str,
                 id: int,
                 test_id: int,
                 **kwargs):
        self.id = id
        self.text = text
        self.test_id = test_id


class Test:
    def __init__(self, 
                 id: int,
                 name: str,
                 test_type: str,
                 results_type: str,
                 instruction_text: str,
                 description: str | None,
                 url: str | None = None,
                 questions: list | None = None,
                 **kwargs):
        self.id = id
        self.name = name
        self.test_type = test_type
        self.results_type = results_type
        self.url = url
        self.instruction_text = instruction_text
        self.description = description
        self.questions = questions

    def question_ids(self) -> list[int]:
        """Return list of question IDs in the test"""
        if not self.questions:
            return []
        return [q["id"] for q in self.questions]
    
    def get_instruction(self) -> str:
        """Return instruction text (append URL if test type is url)"""
        text = ""
        if self.test_type == TestType.url.value:
            text += f"{self.instruction_text}\n{self.url}"
        elif self.test_type == TestType.questions.value:
            text += f"{self.instruction_text}\n{TEST_WITH_QUESTIONS_EXTRA_INFO}"
        
        if self.results_type == TestResultsType.external_processing_result.value:
            text += f"\n\n🆗 Отправьте команду {EXTERNAL_RPOCESSED_TEST_PASSED_COMMAND} когда завершите тест."

        return text


class TestManager:
    def __init__(self, 
                 redis_client: RedisClient, 
                 db_client: APIClient):
        self.redis = redis_client
        self.db = db_client

    # ***********************************************
    #               Tests and questions
    # ***********************************************

    # ---------------- Redis setters ----------------

    async def _set_current_test_id(self, 
                                   telegram_id: str, 
                                   test_id: int):
        """Save current test ID for the user in Redis"""
        key = f"{telegram_id}:on_test"
        return await self.redis.set(key, test_id)
    
    async def _set_current_question_id(self, 
                                       telegram_id: str, question_id: int):
        """Save current question ID for the user in Redis"""
        key = f"{telegram_id}:on_question"
        return await self.redis.set(key, question_id)
    
    # ---------------- DB getters ----------------

    async def _get_test(self, 
                        test_id: int) -> Test | None:
        """Fetch test data from DB by ID"""
        test_data = await self.db.get(Endpoints.get_test, test_id=test_id)
        return Test(**test_data) if test_data else None
    
    async def _get_question(self, 
                            question_id: int) -> Question | None:
        """Fetch question data from DB by ID"""
        question_data = await self.db.get(Endpoints.get_question, question_id=question_id)
        return Question(**question_data) if question_data else None
    
    # ---------------- User-facing methods ----------------

    async def get_current_test(self, 
                               telegram_id: str) -> Test | None:
        """Get the current active test for the user"""
        key = f"{telegram_id}:on_test"
        test_id = await self.redis.get(key)
        if not test_id:
            return None
        return await self._get_test(int(test_id))
    
    async def get_current_question(self, 
                                   telegram_id: str) -> Question | None:
        """Get the current active question for the user"""
        key = f"{telegram_id}:on_question"
        question_id = await self.redis.get(key)
        if not question_id:
            return None
        return await self._get_question(int(question_id))

    async def start_tests(self, 
                          telegram_id: str) -> Test | None:
        """
        Initialize test session for the user:
        - load tests linked to the vacancy
        - save test queue in Redis
        - set the current test and first question
        - return the first test object
        """
        vacancy = await self.db.get(Endpoints.get_vacancy_by_telegram_id, telegram_id=telegram_id)
        if not vacancy:
            return None

        test_ids = await self.db.get(Endpoints.list_tests_for_vacancy, vacancy_id=vacancy["id"])
        if not test_ids:
            return None

        current_test = await self._get_test(test_ids[0])
        if not current_test:
            return None

        # store remaining tests in queue
        if len(test_ids) > 1:
            await self.redis.rpush(f"tests:{telegram_id}", *test_ids[1:])
        await self._set_current_test_id(telegram_id, test_ids[0])

        # if the test has questions — push them into Redis queue
        if current_test.questions:
            question_ids = current_test.question_ids()
            if len(question_ids) > 1:
                await self.redis.rpush(f"questions:{telegram_id}", *question_ids[1:])
            await self._set_current_question_id(telegram_id, question_ids[0])

        return current_test
    
    async def start_questions(self, 
                              telegram_id: str) -> Question | None:
        """Return the first question of the current test"""
        return await self.get_current_question(telegram_id)

    async def next_test(self, telegram_id: str) -> Test | None:
        """
        Switch to the next test in queue:
        - clear current question state
        - pop next test from Redis queue
        - return next test object (if exists)
        """
        await self.redis.delete(f"questions:{telegram_id}")
        await self.redis.delete(f"{telegram_id}:on_question")

        next_test_id = await self.redis.lpop(f"tests:{telegram_id}")
        if not next_test_id:
            await self.redis.delete(f"{telegram_id}:on_test")
            return None
        next_test_id = int(next_test_id)
        next_test = await self._get_test(next_test_id)
        if not next_test:
            return None
        await self._set_current_test_id(telegram_id, next_test_id)
        
        if next_test.questions:
            question_ids = next_test.question_ids()
            await self.redis.rpush(f"questions:{telegram_id}", *question_ids[1:])
            await self._set_current_question_id(telegram_id, question_ids[0])
        return next_test
    
    async def next_question(self, 
                            telegram_id: str) -> Question | None:
        """
        Switch to the next question in queue:
        - pop next question from Redis queue
        - return question object (if exists)
        """
        next_question_id = await self.redis.lpop(f"questions:{telegram_id}")
        if not next_question_id:
            await self.redis.delete(f"{telegram_id}:on_question")
            return None
        
        next_question = await self._get_question(next_question_id)
        if not next_question:
            return None
        await self._set_current_question_id(telegram_id, next_question_id)
        return next_question
    

    # ***********************************************
    #               Test results
    # ***********************************************
    
    async def validate_results(self, message: Message) -> Test | None:
        user_id = str(message.from_user.id)
        logger.info(f"Validating results for user_id={user_id}")

        test = await self.get_current_test(user_id)
        if not test:
            logger.warning(f"No active test found for user_id={user_id}")
            return None

        logger.info(f"Test {test.id} (results_type={test.results_type}) validation started for user_id={user_id}")

        if test.results_type == TestResultsType.text.value:
            if not message.text:
                logger.warning(f"Validation failed: no text provided for user_id={user_id}, test_id={test.id}")
                return None
            logger.info(f"Validation passed: text received for user_id={user_id}, test_id={test.id}")

        elif test.results_type == TestResultsType.screenshot_text.value:
            if not (message.caption and message.photo):
                logger.warning(f"Validation failed: missing text or photo for user_id={user_id}, test_id={test.id}")
                return None
            logger.info(f"Validation passed: text + photo received for user_id={user_id}, test_id={test.id}")

        elif test.results_type == TestResultsType.screenshot.value:
            if not message.photo:
                logger.warning(f"Validation failed: no photo for user_id={user_id}, test_id={test.id}")
                return None
            logger.info(f"Validation passed: photo received for user_id={user_id}, test_id={test.id}")

        elif test.results_type == TestResultsType.external_processing_result.value:
            if not (message.text and message.text.strip() == EXTERNAL_RPOCESSED_TEST_PASSED_COMMAND):
                logger.warning(f"Validation failed: wrong command for external test, user_id={user_id}, test_id={test.id}")
                return None
            logger.info(f"Validation passed: external command confirmed for user_id={user_id}, test_id={test.id}")

        logger.info(f"Validation successful for user_id={user_id}, test_id={test.id}")
        return test
            
        

