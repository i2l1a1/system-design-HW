import asyncio
import logging
import os
import signal

from rental_service.clients.archive_storage import storage_from_env
from rental_service.repository.database import close_db, init_db
from rental_service.services.archive import BATCH_SIZE, RETENTION_DAYS, ArchiveService

logger = logging.getLogger("archive")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    interval = float(os.environ.get("ARCHIVE_INTERVAL_SECONDS", 3600))
    service = ArchiveService(
        storage_from_env(),
        retention_days=int(os.environ.get("ARCHIVE_RETENTION_DAYS", RETENTION_DAYS)),
        batch_size=int(os.environ.get("ARCHIVE_BATCH_SIZE", BATCH_SIZE)),
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signal_number, stop.set)

    init_db()
    try:
        while not stop.is_set():
            try:
                archived, deleted_offers = await service.run_once()
                logger.info("archived orders: %s, deleted unused offers: %s", archived, deleted_offers)
            except Exception:
                logger.exception("archive run failed")
            if os.environ.get("ARCHIVE_RUN_ONCE"):
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                pass
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
