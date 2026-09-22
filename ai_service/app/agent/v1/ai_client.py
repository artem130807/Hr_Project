import time
import json
from typing import Optional, Type

import httpx
from openai import AsyncOpenAI, BadRequestError
from pydantic import BaseModel, ValidationError

from app.agent.v1.errors import AIGenerationError
from app.agent.v1.json_schema import openai_json_schema
from app.app_logging import logger
from app.config import get_outbound_proxy_url


class AIClient:
    def __init__(self, api_key: str, model: str = "gpt-4.1"):
        proxy = get_outbound_proxy_url()
        if proxy:
            logger.info(f"OpenAI client via proxy: {proxy}")
            http_client = httpx.AsyncClient(proxy=proxy, timeout=120.0)
            self.client = AsyncOpenAI(api_key=api_key or "missing-key", http_client=http_client)
        else:
            logger.info("OpenAI client without proxy (TELEGRAM_PROXY_ENABLED=false)")
            self.client = AsyncOpenAI(api_key=api_key or "missing-key")
        self.model = model

    async def generate(
        self,
        prompt: str,
        output_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        use_web_search: bool = False,
    ):
        if use_web_search:
            prompt = (
                "Если это необходимо — используй внешние данные или веб-источники для уточнения информации.\n\n"
                + prompt
            )

        messages = [{"role": "user", "content": prompt}]
        start_time = time.perf_counter()
        try:
            response = await self._create_completion(
                messages=messages,
                temperature=temperature,
                output_model=output_model,
            )
        except BadRequestError as e:
            logger.error(f"[OpenAI API Error] {e}")
            raise AIGenerationError(f"OpenAI bad request: {e}") from e
        except Exception as e:
            logger.exception(f"[AIClient Error] {e}")
            raise AIGenerationError(f"OpenAI request failed: {e}") from e

        duration = time.perf_counter() - start_time
        choice = response.choices[0].message if response and response.choices else None
        content = choice.content if choice else ""

        usage = getattr(response, "usage", None)
        total_tokens = getattr(usage, "total_tokens", None)
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None)

        logger.info(
            f"[AIClient] model={self.model} | web_search={use_web_search} | "
            f"duration={duration:.2f}s | total_tokens={total_tokens} "
            f"(in={input_tokens}, out={output_tokens})"
        )

        if output_model:
            if not content:
                raise AIGenerationError("OpenAI returned empty content")
            try:
                return output_model.model_validate_json(content)
            except ValidationError:
                logger.warning(
                    "[AIClient] Model validation failed. Raw content returned:\n"
                    f"{content[:500]}"
                )
                try:
                    parsed = json.loads(content)
                    return output_model(**parsed)
                except Exception as e:
                    raise AIGenerationError(
                        f"Failed to parse OpenAI JSON into {output_model.__name__}"
                    ) from e

        return content

    async def _create_completion(self, *, messages, temperature, output_model):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if output_model is None:
            kwargs["response_format"] = {"type": "text"}
            return await self.client.chat.completions.create(**kwargs)

        schema = openai_json_schema(output_model)
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": output_model.__name__[:64],
                "strict": True,
                "schema": schema,
            },
        }
        try:
            return await self.client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            logger.warning(
                "[AIClient] json_schema rejected (%s) — retrying with json_object",
                exc,
            )
            kwargs["response_format"] = {"type": "json_object"}
            return await self.client.chat.completions.create(**kwargs)
