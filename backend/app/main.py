from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes.flights import flights_router
from app.clients.ryanair.client import RyanairClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state._ryanairclient = RyanairClient()
    yield

    await app.state._ryanairclient._session.close()


app = FastAPI(lifespan=lifespan)

# Routes
app.include_router(router=flights_router)
