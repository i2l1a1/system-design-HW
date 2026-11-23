import pytest


def test_health(rentals):
    for rental in rentals:
        assert rental.http.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("user", "scooter", "per_minute", "unlock", "deposit"),
    [
        ("plain", "scooter", 24, 45, 300),
        ("sub", "scooter", 24, 0, 300),
        ("trusted", "scooter", 24, 45, 0),
        ("sub-trusted", "scooter-low", 18, 0, 0),
    ],
)
def test_offer_prices(rental, stubs, user_id, user, scooter, per_minute, unlock, deposit):
    offer = rental.create_offer(f"{user}-{user_id}", scooter).json()
    assert (offer["price_per_minute"], offer["price_unlock"], offer["deposit"]) == (per_minute, unlock, deposit)
    assert offer["status"] == "created"


@pytest.mark.parametrize("mode", ["error", "timeout"])
def test_scooters_down_fails_offer(rental, stubs, user_id, mode):
    stubs.set_mode("scooters", mode)
    assert rental.create_offer(user_id).status_code == 503


@pytest.mark.parametrize("mode", ["error", "timeout"])
def test_users_down_uses_antifraud_price(rental, stubs, user_id, mode):
    stubs.set_mode("users", mode)
    offer = rental.create_offer(f"sub-trusted-{user_id}").json()
    assert (offer["price_per_minute"], offer["price_unlock"], offer["deposit"]) == (36, 45, 300)


@pytest.mark.parametrize("source", ["zones", "configs"])
@pytest.mark.parametrize("mode", ["error", "timeout"])
def test_cached_sources_down_keep_offers_working(rentals, stubs, user_id, source, mode):
    for rental in rentals:
        assert rental.create_offer(user_id).status_code == 200
    stubs.set_mode(source, mode)
    for rental in rentals:
        response = rental.create_offer(user_id)
        assert response.status_code == 200, response.text
        assert response.json()["price_per_minute"] == 24
