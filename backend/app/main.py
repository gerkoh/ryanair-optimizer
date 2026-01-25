from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes.flights import (
    all_airports,
    destinations_from_airport,
    cheapest_round_trip_to_destination,
    cheapest_one_way_flight_to_anywhere_this_month,
)
from app.clients.ryanair.client import RyanairClient

from starlette.middleware.sessions import SessionMiddleware
from fastapi import Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from datetime import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state._ryanairclient = RyanairClient()
    yield

    await app.state._ryanairclient._session.close()


app = FastAPI(lifespan=lifespan)

# Frontend setup
SESSION_TIME = 30 * 60
#! Dev settings
app.add_middleware(
    SessionMiddleware,
    secret_key="supersecretkey",
    max_age=SESSION_TIME,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.post("/api/update-session-vars")
async def update_session_vars(
    request: Request,
    origin: str = Form(None),
    availability_start: str = Form(None),
    availability_end: str = Form(None),
    destination: str = Form(None),
    min_travel_days: int = Form(None),
):
    SESSION_VARS = [
        "origin",
        "availability_start",
        "availability_end",
        "destination",
        "min_travel_days",
    ]
    PARAMS = {
        "origin": origin,
        "availability_start": availability_start,
        "availability_end": availability_end,
        "destination": destination,
        "min_travel_days": min_travel_days,
    }

    # Check if origin changed
    origin_changed = PARAMS["origin"] is not None and PARAMS[
        "origin"
    ] != request.session.get("origin")

    # Update session variables
    for var in SESSION_VARS:
        if PARAMS[var] is not None:
            request.session[var] = PARAMS[var]

    # If origin changed, validate and fix destination if needed
    if origin_changed:
        destinations = await destinations_from_airport(
            request.session["origin"], request
        )
        valid_destination_codes = [dest["Code"] for dest in destinations]

        # If current destination is not valid from new origin, select the first available
        if request.session["destination"] not in valid_destination_codes:
            if destinations:
                request.session["destination"] = destinations[0]["Code"]

    return {"status": "success"}


async def initial_load_session(request: Request):
    request.session["origin"] = request.session.get("origin", "STN")
    request.session["availability_start"] = request.session.get(
        "availability_start", str(datetime.now().date())
    )
    request.session["availability_end"] = request.session.get(
        "availability_end",
        str(datetime.now().replace(day=1, month=datetime.now().month + 1).date()),
    )
    request.session["destination"] = request.session.get("destination", "ARN")
    request.session["min_travel_days"] = request.session.get("min_travel_days", 3)


@app.get("/")
async def home_page(request: Request):
    await initial_load_session(request)
    return templates.TemplateResponse(
        "cheapest_round_trip_to_destination.html",
        {
            "request": request,
            "origin": request.session["origin"],
            "availability": {
                "start": request.session["availability_start"],
                "end": request.session["availability_end"],
            },
        },
    )


@app.get("/get_cheapest_one_way_to_anywhere", response_class=HTMLResponse)
async def route_cheapest_one_way_to_anywhere(request: Request):
    await initial_load_session(request)
    return templates.TemplateResponse(
        "cheapest_one_way_to_anywhere.html",
        {
            "request": request,
            "origin": request.session["origin"],
        },
    )


@app.get(
    "/api/search-results/cheapest_one_way_flight_to_anywhere_this_month",
    response_class=HTMLResponse,
)
async def search_results_cheapest_one_way_flight_to_anywhere_this_month(
    request: Request,
):
    return templates.TemplateResponse(
        "partials/one_way_flight_response.html",
        {
            "request": request,
            "origin": request.session["origin"],
            "flights": await cheapest_one_way_flight_to_anywhere_this_month(
                request.session["origin"], request
            ),
        },
    )


@app.get(
    "/api/search-options/cheapest_round_trip_to_destination",
    response_class=HTMLResponse,
)
async def search_options_cheapest_round_trip_to_destination(request: Request):
    return templates.TemplateResponse(
        "partials/searchopt_cheapest_round_trip_to_destination.html",
        {
            "request": request,
            "origin": request.session["origin"],
            "destination": request.session["destination"],
            "min_travel_days": request.session["min_travel_days"],
            "destinations": await destinations_from_airport(
                request.session["origin"], request
            ),
        },
    )


@app.get(
    "/api/search-results/cheapest_round_trip_to_destination",
    response_class=HTMLResponse,
)
async def search_results_cheapest_round_trip_to_destination(request: Request):
    return templates.TemplateResponse(
        "partials/two_way_flight_response.html",
        {
            "request": request,
            "origin": request.session["origin"],
            "destination": request.session["destination"],
            "flights": await cheapest_round_trip_to_destination(
                request.session["origin"],
                request.session["destination"],
                request.session["availability_start"],
                request.session["availability_end"],
                request.session["min_travel_days"],
                request,
            ),
        },
    )


@app.get("/api/all_airports", response_class=HTMLResponse)
async def api_all_airports(request: Request):
    return templates.TemplateResponse(
        "partials/all_airports.html",
        {
            "request": request,
            "origin": request.session["origin"],
            "airports": await all_airports(request),
        },
    )
