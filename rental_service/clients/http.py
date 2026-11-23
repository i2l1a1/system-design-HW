import os

import httpx
from pydantic import BaseModel, ValidationError

stubs = httpx.AsyncClient(base_url=os.environ.get("STUBS_BASE_URL", "http://localhost:3629"), timeout=1.0)


class SourceUnavailable(Exception):
    pass


async def get_model[M: BaseModel](model: type[M], path: str, **params) -> M:
    try:
        response = await stubs.get(path, params=params)
        response.raise_for_status()
        return model.model_validate_json(response.content)
    except (httpx.HTTPError, ValidationError) as error:
        raise SourceUnavailable(path) from error
