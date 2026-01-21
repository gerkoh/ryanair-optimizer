from dotenv import load_dotenv
import os
import aiohttp

load_dotenv()


async def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")
    URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/pair/{from_currency}/{to_currency}"
    async with aiohttp.ClientSession() as session:
        async with session.get(URL) as response:
            if response.status != 200:
                raise ValueError("Failed to fetch exchange rates.")
            data = await response.json()
            if data["result"] != "success":
                raise ValueError("Failed to fetch exchange rates.")
            return data["conversion_rate"]


async def convert_currency(
    from_currency: str, to_currency: str, amount: float
) -> float:
    conversion_rate = await get_exchange_rate(from_currency, to_currency)
    return amount * conversion_rate


if __name__ == "__main__":
    import asyncio

    # FOR TESTING
    async def main():
        converted_amount = await convert_currency("USD", "EUR", 100)
        print(f"Converted Amount: {converted_amount}")

    asyncio.run(main())
