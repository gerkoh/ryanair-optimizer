from fastapi import APIRouter, Request
import datetime
import asyncio
import json

from app.utils.exchange_rate_converter import get_exchange_rate

flights_router = APIRouter(prefix="/api", tags=["flights"])


@flights_router.get("/destinations")
async def all_airports(request: Request):
    """
    Get all available airport destinations that Ryanair services.
    """
    results = json.dumps(await request.app.state._ryanairclient.get_all_airports())
    airport_codes = [airport["code"] for airport in json.loads(results)]
    return airport_codes


@flights_router.get("/cheapest-round-trip-to-destination")
async def cheapest_round_trip_to_destination(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    min_travel_days: int,
    request: Request,
):
    """
    Get the cheapest round trip flight between origin and destination within the availability window.
    """

    # Cast availability window to datetime.date objects
    start_date_obj = datetime.date.fromisoformat(start_date)
    end_date_obj = datetime.date.fromisoformat(end_date)

    # Calculate total months in range
    total_months = (
        (end_date_obj.year - start_date_obj.year) * 12
        + (end_date_obj.month - start_date_obj.month)
        + 1
    )

    # Generate (year, month) pairs
    year_month_pairs = [
        (
            (start_date_obj.year + (start_date_obj.month + i - 1) // 12),
            ((start_date_obj.month + i - 1) % 12) + 1,
        )
        for i in range(total_months)
    ]

    # Create tasks to fetch flight data
    client = request.app.state._ryanairclient
    tasks = [
        client.get_all_flights_in_month_from_airport_to_airport(src, month, year, dst)
        for year, month in year_month_pairs
        for src, dst in [(origin, destination), (destination, origin)]
    ]

    results = await asyncio.gather(*tasks)

    # Split results into outbound and return months, which are interleaved due to the order of tasks
    outbound_months = results[::2]
    return_months = results[1::2]

    # Extract all available outbound flights within date range
    outbound_flights = []
    for month_data in outbound_months:
        if (
            month_data
            and "outbound" in month_data
            and "fares" in month_data["outbound"]
        ):
            for fare in month_data["outbound"]["fares"]:
                if (
                    not fare.get("unavailable")
                    and not fare.get("soldOut")
                    and fare.get("price")
                    and start_date <= fare["day"] <= end_date
                ):
                    outbound_flights.append(fare)

    # Extract all available return flights within date range
    return_flights = []
    for month_data in return_months:
        if (
            month_data
            and "outbound" in month_data
            and "fares" in month_data["outbound"]
        ):
            for fare in month_data["outbound"]["fares"]:
                if (
                    not fare.get("unavailable")
                    and not fare.get("soldOut")
                    and fare.get("price")
                    and start_date <= fare["day"] <= end_date
                ):
                    return_flights.append(fare)

    # Determine conversion rate if needed
    # Optimization: Fetch exchange rate once for all combinations instead of for each one
    conversion_rate = 1.0
    if outbound_flights and return_flights:
        out_currency = outbound_flights[0]["price"]["currencyCode"]
        ret_currency = return_flights[0]["price"]["currencyCode"]
        if out_currency != ret_currency:
            conversion_rate = await get_exchange_rate(ret_currency, out_currency)

    # Create all valid round trip combinations
    round_trips = []

    for outbound in outbound_flights:
        for return_flight in return_flights:
            outbound_date = datetime.date.fromisoformat(outbound["day"])
            return_date = datetime.date.fromisoformat(return_flight["day"])

            # Check minimum travel days constraint
            days_difference = (return_date - outbound_date).days
            if days_difference >= min_travel_days:
                # Calculate total price with conversion
                return_price = return_flight["price"]["value"]
                if conversion_rate != 1.0:
                    return_price *= conversion_rate

                total_price = outbound["price"]["value"] + return_price

                round_trips.append(
                    {
                        "total_price": total_price,
                        "currency": outbound["price"]["currencyCode"],
                        "travel_days": days_difference,
                        "outbound": outbound,
                        "return": return_flight,
                    }
                )

    round_trips.sort(key=lambda x: x["total_price"])

    return round_trips


@flights_router.get("/cheapest-flight-to-anywhere-this-month")
async def cheapest_one_way_flight_to_anywhere_this_month(origin: str, request: Request):
    """
    Get the cheapest one-way flights from origin to any destination for the current month.
    """
    client = request.app.state._ryanairclient
    destinations = await client.get_destinations_from_airport(origin)
    destinations = [dest["arrivalAirport"]["code"] for dest in destinations]
    today = datetime.date.today()
    tasks = [
        client.get_all_flights_in_month_from_airport_to_airport(
            origin, today.month, today.year, destination
        )
        for destination in destinations
    ]
    results = await asyncio.gather(*tasks)

    # Extract all available flights from all destinations
    all_flights = []
    for idx, data in enumerate(results):
        if data and "outbound" in data and "fares" in data["outbound"]:
            destination = destinations[idx]
            for fare in data["outbound"]["fares"]:
                if (
                    not fare.get("unavailable")
                    and not fare.get("soldOut")
                    and fare.get("price")
                ):
                    all_flights.append(
                        {
                            "destination": destination,
                            "day": fare["day"],
                            "departureDate": fare["departureDate"],
                            "arrivalDate": fare["arrivalDate"],
                            "price": fare["price"]["value"],
                            "currency": fare["price"]["currencyCode"],
                            "currencySymbol": fare["price"]["currencySymbol"],
                        }
                    )

    # Sort by price
    all_flights.sort(key=lambda x: x["price"])

    return all_flights


async def cheapest_multi_way_trip():
    pass
