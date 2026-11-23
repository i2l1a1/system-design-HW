from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4


def test_ride_lifecycle(rental, stubs, db, user_id, key, long_ride):
    offer = rental.create_offer(user_id).json()
    order = rental.start(offer["id"]).json()
    assert order["status"] == "active"
    assert db.value("SELECT status FROM offers WHERE id = $1", offer["id"]) == "used"
    assert rental.get(order["id"]).json() == {"id": order["id"], "status": "active", "current_cost": 45}

    long_ride(order["id"])
    assert rental.get(order["id"]).json()["current_cost"] == 45 + 10 * 24

    finished = rental.finish(order["id"], key).json()
    assert finished["status"] == "finished"
    assert finished["total_amount"] == 45 + 10 * 24
    assert rental.get(order["id"]).json() == {"id": order["id"], "status": "finished", "current_cost": 285}
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 100


def test_get_order_does_not_call_stubs(rental, stubs, user_id):
    order = rental.active_order(user_id)
    for source in ("scooters", "zones", "users", "configs", "payments"):
        stubs.set_mode(source, "error")
    assert rental.get(order["id"]).status_code == 200


def test_start_is_idempotent_by_offer(rentals, stubs, db, user_id):
    offer = rentals[0].create_offer(user_id).json()
    with ThreadPoolExecutor(16) as pool:
        responses = list(pool.map(lambda i: rentals[i % len(rentals)].start(offer["id"]), range(32)))
    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["id"] for response in responses}) == 1
    assert db.value("SELECT count(*) FROM orders WHERE offer_id = $1", offer["id"]) == 1
    assert db.value("SELECT count(*) FROM payment_operations WHERE order_id = $1", responses[0].json()["id"]) == 1


def test_unknown_offer_and_order(rental, stubs, key):
    assert rental.start("missing").status_code == 404
    assert rental.get("missing").status_code == 404
    assert rental.finish("missing", key).status_code == 404


def test_expired_offer(rental, stubs, db, user_id):
    offer = rental.create_offer(user_id).json()
    db.fetch("UPDATE offers SET created_at = created_at - interval '10 minutes' WHERE id = $1", offer["id"])
    assert rental.start(offer["id"]).status_code == 410
    assert db.value("SELECT status FROM offers WHERE id = $1", offer["id"]) == "expired"
    assert rental.start(offer["id"]).status_code == 410
    assert db.value("SELECT count(*) FROM orders WHERE offer_id = $1", offer["id"]) == 0


def test_declined_hold_releases_offer(rental, stubs, db, user_id):
    offer = rental.create_offer(user_id).json()
    stubs.set_mode("payments", "decline")
    assert rental.start(offer["id"]).status_code == 402
    assert db.value("SELECT status FROM offers WHERE id = $1", offer["id"]) == "created"
    assert db.value("SELECT count(*) FROM orders WHERE offer_id = $1", offer["id"]) == 0

    stubs.set_mode("payments", "ok")
    assert rental.start(offer["id"]).json()["status"] == "active"


def test_unknown_hold_is_resumed_by_retry(rental, stubs, db, user_id, key):
    offer = rental.create_offer(user_id).json()
    stubs.set_mode("payments", "unknown")
    pending = rental.start(offer["id"])
    assert pending.status_code == 202
    assert pending.json()["status"] == "pending_start"
    order_id = pending.json()["id"]
    assert db.value("SELECT status FROM offers WHERE id = $1", offer["id"]) == "reserved"
    assert db.value("SELECT status FROM payment_operations WHERE order_id = $1", order_id) == "unknown"
    assert rental.get(order_id).json()["current_cost"] == 0
    assert rental.finish(order_id, key).status_code == 409

    stubs.set_mode("payments", "ok")
    resumed = rental.start(offer["id"])
    assert resumed.status_code == 200
    assert resumed.json() == {**pending.json(), "status": "active", "start_time": resumed.json()["start_time"]}
    assert db.value("SELECT status FROM payment_operations WHERE order_id = $1", order_id) == "success"
    assert db.value("SELECT status FROM offers WHERE id = $1", offer["id"]) == "used"


def test_short_ride_is_cancelled_for_free(rental, stubs, db, user_id, key):
    order = rental.active_order(user_id)
    cancelled = rental.finish(order["id"], key).json()
    assert (cancelled["status"], cancelled["total_amount"]) == ("cancelled", 0)
    assert rental.get(order["id"]).json()["current_cost"] == 0
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) is None
    assert db.value("SELECT count(*) FROM debts WHERE user_id = $1", user_id) == 0


def test_finish_is_idempotent(rentals, stubs, db, user_id, key, long_ride):
    db.fetch("INSERT INTO user_reliability VALUES ($1, 50, now())", user_id)
    order = rentals[0].active_order(user_id)
    long_ride(order["id"])
    keys = [key, key, uuid4().hex, uuid4().hex]
    with ThreadPoolExecutor(16) as pool:
        responses = list(
            pool.map(lambda i: rentals[i % len(rentals)].finish(order["id"], keys[i % len(keys)]), range(32))
        )
    assert {response.status_code for response in responses} == {200}
    assert len({response.text for response in responses}) == 1
    assert db.value("SELECT count(*) FROM payment_operations WHERE order_id = $1 AND type = 'clear'", order["id"]) == 1
    assert db.value("SELECT count(*) FROM idempotency_keys WHERE order_id = $1", order["id"]) == 1
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 51


def test_idempotency_key_of_another_order(rental, stubs, user_id, key, long_ride):
    first, second = rental.active_order(user_id), rental.active_order(user_id)
    assert rental.finish(first["id"], key).status_code == 200
    assert rental.finish(second["id"], key).status_code == 409
    assert rental.get(second["id"]).json()["status"] == "active"


def test_unknown_clear_is_resumed_by_retry(rental, stubs, db, user_id, key, long_ride):
    db.fetch("INSERT INTO user_reliability VALUES ($1, 50, now())", user_id)
    order = rental.active_order(user_id)
    long_ride(order["id"])

    stubs.set_mode("payments", "unknown")
    finished = rental.finish(order["id"], key)
    assert finished.json()["status"] == "finished"
    assert db.value("SELECT result FROM idempotency_keys WHERE key = $1", key) is None
    assert db.value("SELECT status FROM payment_operations WHERE payment_key = $1", f"clear:{order['id']}") == "unknown"
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 50

    stubs.set_mode("payments", "ok")
    for _ in range(3):
        assert rental.finish(order["id"], key).json() == finished.json()
    assert db.value("SELECT result FROM idempotency_keys WHERE key = $1", key) == "success"
    assert db.value("SELECT status FROM payment_operations WHERE payment_key = $1", f"clear:{order['id']}") == "success"
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 51
