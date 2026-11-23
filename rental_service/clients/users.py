from pydantic import BaseModel

from rental_service.clients.http import get_model


class UserProfile(BaseModel):
    id: str
    has_subscription: bool
    trusted: bool


class UsersClient:
    async def get_user_profile(self, user_id: str) -> UserProfile:
        return await get_model(UserProfile, "/user-profile", id=user_id)
