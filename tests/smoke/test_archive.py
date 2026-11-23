import asyncio
import gzip
import json
import os

import pytest

from rental_service.clients.archive_storage import FileArchiveStorage
from rental_service.repository.database import close_db, init_db
from rental_service.services.archive import ArchiveService

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://rental:rental@localhost:5432/rental")


@pytest.fixture
def archive(tmp_path):
    def run() -> dict[str, dict]:
        async def run_once():
            init_db(DATABASE_URL)
            try:
                await ArchiveService(FileArchiveStorage(str(tmp_path)), batch_size=2).run_once()
            finally:
                await close_db()

        asyncio.run(run_once())
        records = {}
        for path in tmp_path.rglob("*.jsonl.gz"):
            assert path.parent.name.startswith("dt=")
            for line in gzip.decompress(path.read_bytes()).decode().splitlines():
                record = json.loads(line)
                assert record["order"]["id"] not in records
                records[record["order"]["id"]] = record
        return records

    return run


@pytest.fixture
def old(db):
    def shift(order_id: str) -> None:
        db.fetch(
            "UPDATE orders SET start_time = start_time - interval '40 days', "
            "finish_time = finish_time - interval '40 days' WHERE id = $1",
            order_id,
        )

    return shift


def finished_order(rental, user_id, key, long_ride) -> dict:
    order = rental.active_order(user_id)
    long_ride(order["id"])
    return rental.finish(order["id"], key).json()


def test_old_closed_orders_move_to_archive(rental, stubs, db, archive, old, user_id, key, long_ride):
    archived = [finished_order(rental, f"{user_id}-{i}", f"{key}-{i}", long_ride) for i in range(3)]
    cancelled = rental.active_order(user_id)
    rental.finish(cancelled["id"], f"{key}-cancelled")
    recent = finished_order(rental, user_id, f"{key}-recent", long_ride)
    active = rental.active_order(user_id)
    for order in (*archived, cancelled, active):
        old(order["id"])

    records = archive()

    for order in (*archived, cancelled):
        record = records[order["id"]]
        assert record["order"]["status"] in ("finished", "cancelled")
        assert record["offer"]["id"] == order["offer_id"]
        assert {payment["type"] for payment in record["payments"]} == {"hold", "clear"}
        assert len(record["idempotency_keys"]) == 1
        assert rental.get(order["id"]).status_code == 404
        assert db.value("SELECT count(*) FROM offers WHERE id = $1", order["offer_id"]) == 0
        assert db.value("SELECT count(*) FROM payment_operations WHERE order_id = $1", order["id"]) == 0
        assert db.value("SELECT count(*) FROM idempotency_keys WHERE order_id = $1", order["id"]) == 0
    for order in (recent, active):
        assert order["id"] not in records
        assert rental.get(order["id"]).status_code == 200


def test_order_with_unpaid_debt_stays_until_repaid(rental, stubs, db, archive, old, user_id, key, long_ride):
    stubs.set_mode("payments", "ok")
    order = rental.active_order(user_id)
    long_ride(order["id"])
    stubs.set_mode("payments", "decline")
    rental.finish(order["id"], key)
    stubs.set_mode("payments", "ok")
    old(order["id"])

    assert order["id"] not in archive()
    assert rental.start(rental.create_offer(user_id).json()["id"]).status_code == 403

    (debt,) = rental.debts(user_id).json()
    rental.repay(debt["id"])
    record = archive()[order["id"]]
    assert [(item["id"], item["status"]) for item in record["debts"]] == [(debt["id"], "repaid")]
    assert db.value("SELECT count(*) FROM debts WHERE id = $1", debt["id"]) == 0


def test_order_with_unknown_payment_stays(rental, stubs, archive, old, user_id, key, long_ride):
    order = rental.active_order(user_id)
    long_ride(order["id"])
    stubs.set_mode("payments", "unknown")
    rental.finish(order["id"], key)
    old(order["id"])

    assert order["id"] not in archive()

    stubs.set_mode("payments", "ok")
    rental.finish(order["id"], key)
    assert order["id"] in archive()


def test_unused_old_offers_are_deleted(rental, stubs, db, archive, user_id):
    stale, fresh = rental.create_offer(user_id).json(), rental.create_offer(user_id).json()
    db.fetch("UPDATE offers SET created_at = created_at - interval '40 days' WHERE id = $1", stale["id"])
    archive()
    assert db.value("SELECT count(*) FROM offers WHERE id = $1", stale["id"]) == 0
    assert db.value("SELECT count(*) FROM offers WHERE id = $1", fresh["id"]) == 1
