import asyncio
import os
from uuid import uuid4

import asyncpg
import httpx
import pytest

RENTAL_URLS = os.environ.get("RENTAL_URLS", "http://localhost:8000,http://localhost:8001").split(",")
STUBS_URL = os.environ.get("STUBS_URL", "http://localhost:3629")
DATABASE_DSN = os.environ.get("DATABASE_DSN", "postgresql://rental:rental@localhost:5432/rental")
SOURCES = ("scooters", "zones", "users", "configs", "payments")


class Database:
    def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        async def run():
            connection = await asyncpg.connect(DATABASE_DSN)
            try:
                return await connection.fetch(query, *args)
            finally:
                await connection.close()

        return asyncio.run(run())

    def value(self, query: str, *args):
        rows = self.fetch(query, *args)
        return rows[0][0] if rows else None


class Stubs:
    def __init__(self) -> None:
        self.http = httpx.Client(base_url=STUBS_URL, timeout=10)

    def set_mode(self, source: str, mode: str) -> None:
        self.http.put(f"/modes/{source}", params={"mode": mode}).raise_for_status()

    def reset(self) -> None:
        for source in SOURCES:
            self.set_mode(source, "ok")


class Rental:
    def __init__(self, base_url: str) -> None:
        self.http = httpx.Client(base_url=base_url, timeout=15)

    def create_offer(self, user_id: str, scooter_id: str = "scooter") -> httpx.Response:
        return self.http.post("/offers", json={"user_id": user_id, "scooter_id": scooter_id})

    def start(self, offer_id: str) -> httpx.Response:
        return self.http.post("/orders", json={"offer_id": offer_id})

    def finish(self, order_id: str, key: str) -> httpx.Response:
        return self.http.post(f"/orders/{order_id}/finish", json={"idempotency_key": key})

    def get(self, order_id: str) -> httpx.Response:
        return self.http.get(f"/orders/{order_id}")

    def debts(self, user_id: str) -> httpx.Response:
        return self.http.get(f"/users/{user_id}/debts")

    def repay(self, debt_id: str) -> httpx.Response:
        return self.http.post(f"/debts/{debt_id}/repay")

    def active_order(self, user_id: str) -> dict:
        offer = self.create_offer(user_id).json()
        response = self.start(offer["id"])
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture(scope="session")
def db() -> Database:
    return Database()


@pytest.fixture(scope="session")
def rental() -> Rental:
    return Rental(RENTAL_URLS[0])


@pytest.fixture(scope="session")
def rentals() -> list[Rental]:
    return [Rental(url) for url in RENTAL_URLS]


@pytest.fixture
def stubs():
    stubs = Stubs()
    stubs.reset()
    yield stubs
    stubs.reset()


@pytest.fixture
def user_id() -> str:
    return f"user-{uuid4().hex[:12]}"


@pytest.fixture
def key() -> str:
    return uuid4().hex


@pytest.fixture
def long_ride(db):
    def shift(order_id: str, minutes: int = 10) -> None:
        db.fetch("UPDATE orders SET start_time = start_time - make_interval(mins => $2) WHERE id = $1", order_id, minutes)

    return shift
