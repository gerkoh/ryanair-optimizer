from fastapi import Request
import datetime
import asyncio
import json

from app.utils.exchange_rate_converter import convert_currency


async def all_airports(request: Request):
    """
    Get all available airport destinations that Ryanair services.
    """
    results = json.dumps(await request.app.state._ryanairclient.get_all_airports())
    airport_codes = [
        {"Code": airport["code"], "Name": airport["name"]}
        for airport in json.loads(results)
    ]
    return airport_codes


async def destinations_from_airport(origin: str, request: Request):
    """
    Get all available destinations from a given origin airport.
    """
    results = await request.app.state._ryanairclient.get_destinations_from_airport(
        origin
    )
    destination_codes = [
        {
            "Code": destination["arrivalAirport"]["code"],
            "Name": destination["arrivalAirport"]["name"],
        }
        for destination in results
    ]
    return destination_codes


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

    # Create all valid round trip combinations
    valid_combinations = []
    conversion_tasks = []  # may be required
    conversion_indices = []  # may be required

    for outbound in outbound_flights:
        for return_flight in return_flights:
            outbound_date = datetime.date.fromisoformat(outbound["day"])
            return_date = datetime.date.fromisoformat(return_flight["day"])

            # Check minimum travel days constraint
            days_difference = (return_date - outbound_date).days
            if days_difference >= min_travel_days:
                combination = {
                    "outbound": outbound,
                    "return": return_flight,
                    "travel_days": days_difference,
                }

                # Check if currency conversion is needed
                if (
                    outbound["price"]["currencyCode"]
                    != return_flight["price"]["currencyCode"]
                ):
                    # Add conversion task
                    conversion_tasks.append(
                        convert_currency(
                            return_flight["price"]["currencyCode"],
                            outbound["price"]["currencyCode"],
                            return_flight["price"]["value"],
                        )
                    )
                    conversion_indices.append(len(valid_combinations))

                valid_combinations.append(combination)

    # Convert currencies if needed (EUR as base)
    if conversion_tasks:
        converted_values = await asyncio.gather(*conversion_tasks)

        # Re-apply converted values prices to valid_combinations
        for idx, converted_value in zip(conversion_indices, converted_values):
            valid_combinations[idx]["converted_return_value"] = converted_value

    # Calculate and sort total prices
    round_trips = []
    for combination in valid_combinations:
        outbound = combination["outbound"]
        return_flight = combination["return"]

        if "converted_return_value" in combination:
            total_price = (
                outbound["price"]["value"] + combination["converted_return_value"]
            )
        else:
            total_price = outbound["price"]["value"] + return_flight["price"]["value"]

        round_trips.append(
            {
                "total_price": total_price,
                "currency": outbound["price"]["currencyCode"],
                "travel_days": combination["travel_days"],
                "outbound": outbound,
                "return": return_flight,
            }
        )

    round_trips.sort(key=lambda x: x["total_price"])

    return round_trips


async def cheapest_one_way_flight_to_anywhere_this_month(origin: str, request: Request):
    """
    Get the cheapest one-way flights from origin to any destination for the current month.
    """
    client = request.app.state._ryanairclient
    destinations = await client.get_destinations_from_airport(origin)
    destinations = [
        (dest["arrivalAirport"]["code"], dest["arrivalAirport"]["name"])
        for dest in destinations
    ]
    today = datetime.date.today()
    tasks = [
        client.get_all_flights_in_month_from_airport_to_airport(
            origin, today.month, today.year, destination[0]
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
                            "destination_code": destination[0],
                            "destination_name": destination[1],
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
