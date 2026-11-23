from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Protocol


class ArchiveStorage(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...


class FileArchiveStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self._write, key, data)

    def _write(self, key: str, data: bytes) -> None:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)


class S3ArchiveStorage:
    def __init__(self, bucket: str, endpoint_url: str | None = None) -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client("s3", endpoint_url=endpoint_url)

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self._client.put_object, Bucket=self._bucket, Key=key, Body=data)


def storage_from_env() -> ArchiveStorage:
    bucket = os.environ.get("ARCHIVE_S3_BUCKET")
    if bucket:
        return S3ArchiveStorage(bucket, os.environ.get("ARCHIVE_S3_ENDPOINT"))
    return FileArchiveStorage(os.environ.get("ARCHIVE_DIR", "archive"))
