class OrderService:
    async def start_order(self, offer_id: str):
        raise NotImplementedError

    async def finish_order(self, order_id: str, idempotency_key: str):
        raise NotImplementedError

    async def get_order(self, order_id: str):
        raise NotImplementedError
