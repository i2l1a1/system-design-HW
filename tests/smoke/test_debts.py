from uuid import uuid4

import pytest


@pytest.fixture
def debt(rental, stubs, user_id, key, long_ride) -> dict:
    order = rental.active_order(user_id)
    long_ride(order["id"])
    stubs.set_mode("payments", "decline")
    assert rental.finish(order["id"], key).json()["status"] == "finished"
    stubs.set_mode("payments", "ok")
    (debt,) = rental.debts(user_id).json()
    return debt


def test_declined_clear_creates_debt(rental, db, user_id, debt, key):
    assert (debt["amount"], debt["status"]) == (285, "unpaid")
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 80

    assert rental.finish(debt["order_id"], key).status_code == 200
    assert len(rental.debts(user_id).json()) == 1
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 80


def test_debt_blocks_new_orders_until_repaid(rental, db, user_id, debt):
    offer = rental.create_offer(user_id).json()
    assert rental.start(offer["id"]).status_code == 403
    assert db.value("SELECT status FROM offers WHERE id = $1", offer["id"]) == "created"

    for _ in range(2):
        repaid = rental.repay(debt["id"])
        assert repaid.status_code == 200
        assert repaid.json()["status"] == "repaid"
    assert rental.debts(user_id).json() == []
    assert db.value("SELECT score FROM user_reliability WHERE user_id = $1", user_id) == 90
    assert rental.start(offer["id"]).json()["status"] == "active"


def test_repay_unknown_debt(rental, stubs):
    assert rental.repay("missing").status_code == 404


@pytest.fixture
def tight_mode(rental, stubs, db):
    order = rental.active_order(f"debtor-{uuid4().hex[:12]}")
    debt_id = uuid4().hex
    db.fetch(
        "INSERT INTO debts VALUES ($1, $2, $3, 200000, 'unpaid', now(), NULL)", debt_id, order["user_id"], order["id"]
    )
    yield
    db.fetch("DELETE FROM debts WHERE id = $1", debt_id)


def test_tight_mode(rental, db, user_id, tight_mode):
    trusted, unreliable = f"trusted-{user_id}", f"trusted-low-{user_id}"
    db.fetch("INSERT INTO user_reliability VALUES ($1, 69, now())", unreliable)

    offer = rental.create_offer(trusted).json()
    assert offer["deposit"] == 300
    assert rental.start(offer["id"]).status_code == 200

    rejected = rental.start(rental.create_offer(unreliable).json()["id"])
    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "user score is too low"
