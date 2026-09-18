import httpx


class RedfishClient:
    """Small async Redfish HTTP client for one BMC."""

    def __init__(
        self,
        base_url,
        username,
        password,
        *,
        verify_ssl=False,
        timeout=10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            auth=(username, password),
            verify=verify_ssl,
            timeout=httpx.Timeout(timeout),
        )

    async def get(self, path):
        url = (
            path
            if path.startswith("http")
            else "{}/{}".format(self.base_url, path.lstrip("/"))
        )
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()
