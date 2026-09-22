import httpx
from app.app_logging import logger
from app.utils.auth_token_manager import TokenManager


class APICLient:
    def __init__(self, 
                 base_url: str,
                 token_manager: TokenManager,
                 timeout: float = 5.0, 
                 headers_required: bool = True):
        self.base_url = base_url
        self.timeout = timeout
        self.token_manager = token_manager
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self.headers_required = headers_required

    def _build_url(self, url_template, **url_params):
        return url_template.format(**url_params)
    
    async def _get_headers(self):
        access_token = await self.token_manager.get_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        return headers

    async def _request(self, method, url_template, **request_kwargs):
        # Отделяем параметры URL от параметров запроса
        url_params = {k: v for k, v in request_kwargs.items() 
                     if k not in ['json', 'data', 'headers', 'params']}
        
        url = self._build_url(url_template, **url_params)
        
        # Подготавливаем параметры для httpx
        httpx_kwargs = {}
        for key in ['json', 'data', 'headers', 'params']:
            if key in request_kwargs:
                httpx_kwargs[key] = request_kwargs[key]

        try:
            if self.headers_required:
                headers = await self._get_headers()
                response = await self.client.request(method=method, url=url, headers=headers, **httpx_kwargs)
            else:
                response = await self.client.request(method, url, **httpx_kwargs)
            response.raise_for_status()
            logger.info(f"Successful {method} request to {url}")
            return response.json()
        except httpx.HTTPStatusError as e:
            if 400 <= e.response.status_code < 500:
                logger.error(f"Client error {e.response.status_code} for {url}")
                return None
            elif 500 <= e.response.status_code < 600:
                logger.error(f"Server error {e.response.status_code} for {url}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
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