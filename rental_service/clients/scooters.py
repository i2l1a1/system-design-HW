from pydantic import BaseModel

from rental_service.clients.http import get_model


class ScooterData(BaseModel):
    id: str
    zone_id: str
    charge: int


class ScootersClient:
    async def get_scooter_data(self, scooter_id: str) -> ScooterData:
        return await get_model(ScooterData, "/scooter-data", id=scooter_id)
