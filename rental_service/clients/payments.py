class PaymentsClient:
    async def hold_money_for_order(self, user_id: str, order_id: str, amount: int):
        raise NotImplementedError

    async def clear_money_for_order(self, user_id: str, order_id: str, amount: int):
        raise NotImplementedError
