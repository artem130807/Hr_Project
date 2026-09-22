import httpx

from app.app_logging import logger
from app.utils.auth_token_manager import TokenManager


class UpstreamHTTPError(Exception):
    def __init__(self, status_code: int, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail



class APICLient:
    def __init__(
        self,
        base_url: str,
        token_manager: TokenManager,
        timeout: float = 5.0,
        headers_required: bool = True,
        internal_token: str | None = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.token_manager = token_manager
        self.client = httpx.AsyncClient(timeout=timeout)
        self.headers_required = headers_required
        self.internal_token = (internal_token or "").strip() or None

    def _build_url(self, url_template, **url_params):
        return self.base_url + url_template.format(**url_params)
    
    async def _get_headers(self):
        access_token = await self.token_manager.get_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token
        return headers

    async def _request(self, method, url_template, **request_kwargs):
        # Отделяем параметры URL от параметров запроса
        url_params = {k: v for k, v in request_kwargs.items()
                     if k not in ['json', 'data', 'headers', 'params', 'timeout', 'raise_http']}

        url = self._build_url(url_template, **url_params)

        httpx_kwargs = {}
        for key in ['json', 'data', 'headers', 'params']:
            if key in request_kwargs:
                httpx_kwargs[key] = request_kwargs[key]
        timeout = request_kwargs.get("timeout", self.timeout)
        raise_http = bool(request_kwargs.get("raise_http"))
        httpx_kwargs["timeout"] = timeout

        try:
            if self.headers_required:
                headers = await self._get_headers()
                extra = httpx_kwargs.pop("headers", None)
                if extra:
                    headers = {**headers, **extra}
                response = await self.client.request(method=method, url=url, headers=headers, **httpx_kwargs)
            else:
                response = await self.client.request(method, url, **httpx_kwargs)
            response.raise_for_status()
            logger.info(f"Successful {method} request to {url}")
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                logger.warning(f"Non-JSON response from {url}")
                return {"status": "ok"}
        except httpx.TimeoutException as e:
            logger.error("Timeout for %s %s: %s", method, url, e)
            if raise_http:
                raise UpstreamHTTPError(504, "AI service timeout") from e
            return None
        except httpx.HTTPStatusError as e:
            if raise_http:
                detail = e.response.text
                try:
                    body = e.response.json()
                    detail = body.get("detail", detail) if isinstance(body, dict) else body
                except ValueError:
                    pass
                status = e.response.status_code
                if status in (401, 403):
                    logger.error("Upstream auth failed for %s %s: %s", method, url, detail)
                    raise UpstreamHTTPError(502, f"AI service auth failed: {detail}") from e
                if status >= 500:
                    status = 502 if status != 504 else 504
                raise UpstreamHTTPError(status, detail) from e
            if 400 <= e.response.status_code < 500:
                logger.error(f"Client error {e.response.status_code} for {url}")
                return None
            elif 500 <= e.response.status_code < 600:
                logger.error(f"Server error {e.response.status_code} for {url}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            if raise_http:
                raise UpstreamHTTPError(502, "AI service unavailable") from e
            return None

    async def get(self, url_template, **kwargs):
        return await self._request('GET', url_template, **kwargs)

    async def post(self, url_template, **kwargs):
        return await self._request('POST', url_template, **kwargs)

    async def put(self, url_template, **kwargs):
        return await self._request('PUT', url_template, **kwargs)
    
    async def patch(self, url_template, **kwargs):
        return await self._request('PATCH', url_template, **kwargs)

    async def delete(self, url_template, **kwargs):
        return await self._request('DELETE', url_template, **kwargs)

    async def close(self):
        await self.client.aclose()
