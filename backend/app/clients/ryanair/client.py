import aiohttp


class RyanairClient:
    def __init__(self):
        self._session = self._build_session()

    def _build_session(self) -> aiohttp.ClientSession:
        """
        Builds and returns an aiohttp ClientSession configured with Ryanair base URL.
        """
        BASE_URL = "https://www.ryanair.com/api/"
        connector = aiohttp.TCPConnector(
            keepalive_timeout=30,
        )

        return aiohttp.ClientSession(
            base_url=BASE_URL, connector=connector, raise_for_status=True
        )

    async def safe_get(self, url: str):
        """
        Wrapper for making safe GET requests to the Ryanair API.
        """
        try:
            async with self._session.get(url) as response:
                if response.status >= 500:
                    raise RuntimeError(f"Server error: {response.status}")
                if response.status >= 400:
                    raise RuntimeError(f"Client error {response.status}")

                return await response.json()

        except aiohttp.ClientError as e:
            raise RuntimeError(f"Error {e}: Transport error")

        except TimeoutError as e:
            raise RuntimeError(f"Error {e}: Runtime error")

    async def get_destinations_from_airport(
        self,
        origin: str,
    ):
        url = f"views/locate/searchWidget/routes/en/airport/{origin.upper()}"

        return await self.safe_get(url)

    async def get_all_flights_in_month_from_airport_to_airport(
        self,
        origin: str,
        month: int,
        year: int,
        destination: str,
        currency: str = "EUR",
    ):
        departDate = f"{year}-{month:02d}-01"
        url = f"farfnd/v4/oneWayFares/{origin.upper()}/{destination.upper()}/cheapestPerDay?outboundMonthOfDate={departDate}&currency={currency}"

        return await self.safe_get(url)

    async def get_all_airports(self):
        url = "views/locate/5/airports/en/active"

        return await self.safe_get(url)
