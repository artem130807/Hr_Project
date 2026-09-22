import time
import httpx
from app.app_logging import logger
from app.utils.auth_token_manager import TokenManager


class APIClient:
    def __init__(self, 
                 base_url: str,
                 token_manager: TokenManager,
                 timeout: float = 5.0, 
                 headers_required: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token_manager = token_manager
        self.client = httpx.AsyncClient(timeout=timeout)
        self.headers_required = headers_required

    def _build_url(self, url_template, **url_params):
        path = url_template.format(**url_params)
        return self.base_url.rstrip('/') + '/' + path.lstrip('/')
    
    async def _get_headers(self):
        access_token = await self.token_manager.get_token()
        return {"Authorization": f"Bearer {access_token}"}

    async def _request(self, method, url_template, **request_kwargs):
        url_params = {k: v for k, v in request_kwargs.items()
                     if k not in ['json', 'data', 'headers', 'params', 'files', 'content']}
        url = self._build_url(url_template, **url_params)

        httpx_kwargs = {k: v for k, v in request_kwargs.items()
                        if k in ['json', 'data', 'headers', 'params', 'files', 'content']}

        start_time = time.perf_counter()  # 🕒 старт
        try:
            if self.headers_required:
                headers = await self._get_headers()
                response = await self.client.request(method=method, url=url, headers=headers, **httpx_kwargs)
            else:
                response = await self.client.request(method, url, **httpx_kwargs)

            elapsed = (time.perf_counter() - start_time) * 1000  # в миллисекундах
            logger.info(f"HTTP {method} {url} completed in {elapsed:.2f} ms with status {response.status_code}")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(f"HTTP {method} {url} failed in {elapsed:.2f} ms — {e.response.status_code}")
            return None

        except httpx.RequestError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(f"HTTP {method} {url} request error in {elapsed:.2f} ms — {e}")
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

    async def post_file(self, url_template, image_bytes: bytes, content_type: str = "image/jpeg", **url_params):
        url = self._build_url(url_template, **url_params)
        start_time = time.perf_counter()
        try:
            headers = await self._get_headers() if self.headers_required else {}
            files = {"file": ("image.jpg", image_bytes, content_type)}
            response = await self.client.post(url, headers=headers, files=files)
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(f"HTTP POST (file) {url} completed in {elapsed:.2f} ms with status {response.status_code}")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(f"HTTP POST (file) {url} failed in {elapsed:.2f} ms — {e.response.status_code}")
            return False
        except httpx.RequestError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(f"HTTP POST (file) {url} request error in {elapsed:.2f} ms — {e}")
            return False

    async def close(self):
        await self.client.aclose()
