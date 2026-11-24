import argparse
import asyncio
import csv
import json
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from uuid import uuid4

import aiohttp

ENDPOINTS = ("POST /offers", "POST /orders", "GET /orders/{id}", "POST /orders/{id}/finish")


@dataclass(frozen=True)
class Sample:
    at: float
    endpoint: str
    status: int
    seconds: float


class Emulator:
    def __init__(self, session: aiohttp.ClientSession, base_urls: list[str], views: int, ride_seconds: float) -> None:
        self.session = session
        self.base_urls = cycle(base_urls)
        self.views = views
        self.ride_seconds = ride_seconds
        self.samples: list[Sample] = []
        self.rides = defaultdict(int)
        self.started_at = time.perf_counter()

    async def request(self, endpoint: str, method: str, path: str, body: dict | None = None) -> dict | None:
        started = time.perf_counter()
        status, payload = 0, None
        try:
            async with self.session.request(method, next(self.base_urls) + path, json=body) as response:
                status = response.status
                payload = await response.json() if status == 200 else await response.read() and None
        except (aiohttp.ClientError, TimeoutError):
            pass
        self.samples.append(Sample(started - self.started_at, endpoint, status, time.perf_counter() - started))
        return payload

    async def ride(self) -> None:
        self.rides["started"] += 1
        user_id, scooter_id = f"load-{uuid4().hex}", f"scooter-{uuid4().hex[:8]}"
        offer = await self.request(ENDPOINTS[0], "POST", "/offers", {"user_id": user_id, "scooter_id": scooter_id})
        order = offer and await self.request(ENDPOINTS[1], "POST", "/orders", {"offer_id": offer["id"]})
        if not order:
            self.rides["failed"] += 1
            return
        pause = self.ride_seconds / self.views
        for _ in range(self.views):
            await asyncio.sleep(pause)
            await self.request(ENDPOINTS[2], "GET", f"/orders/{order['id']}")
        finished = await self.request(
            ENDPOINTS[3], "POST", f"/orders/{order['id']}/finish", {"idempotency_key": uuid4().hex}
        )
        self.rides["finished" if finished else "failed"] += 1

    async def run(self, rps: float, duration: float) -> None:
        rides = []
        for number in range(int(rps * duration)):
            delay = self.started_at + number / rps - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            rides.append(asyncio.create_task(self.ride()))
        await asyncio.gather(*rides)


async def docker_stats(path: Path, started_at: float, stop: asyncio.Event, interval: float) -> None:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("at", "container", "cpu_percent", "memory_mib"))
        while not stop.is_set():
            try:
                process = await asyncio.create_subprocess_exec(
                    "docker", "stats", "--no-stream", "--format", "{{.Name}};{{.CPUPerc}};{{.MemUsage}}",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                )
            except OSError:
                return
            output, _ = await process.communicate()
            at = time.perf_counter() - started_at
            for line in output.decode().splitlines():
                name, cpu, memory = line.split(";")
                writer.writerow((f"{at:.1f}", name, cpu.rstrip("%"), to_mib(memory.split("/")[0].strip())))
            try:
                await asyncio.wait_for(stop.wait(), interval)
            except TimeoutError:
                pass


def to_mib(value: str) -> float:
    for suffix, factor in (("GiB", 1024), ("MiB", 1), ("KiB", 1 / 1024), ("B", 1 / 1024**2)):
        if value.endswith(suffix):
            return round(float(value.removesuffix(suffix)) * factor, 1)
    return 0.0


def percentile(values: list[float], share: float) -> float:
    return values[min(len(values) - 1, int(len(values) * share))]


def summarize(emulator: Emulator, arguments: argparse.Namespace, elapsed: float) -> dict:
    endpoints = {}
    for endpoint in ENDPOINTS:
        samples = [sample for sample in emulator.samples if sample.endpoint == endpoint]
        latencies = sorted(sample.seconds * 1000 for sample in samples)
        statuses = defaultdict(int)
        for sample in samples:
            statuses[str(sample.status)] += 1
        endpoints[endpoint] = {
            "requests": len(samples),
            "rps": round(len(samples) / arguments.duration, 1),
            "errors": len(samples) - statuses["200"],
            "statuses": dict(statuses),
            "latency_ms": {
                "mean": round(statistics.fmean(latencies), 2),
                "p50": round(percentile(latencies, 0.50), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "p99": round(percentile(latencies, 0.99), 2),
                "max": round(latencies[-1], 2),
            } if latencies else {},
        }
    return {
        "parameters": {
            "orders_rps": arguments.rps,
            "views_per_order": arguments.views,
            "duration_seconds": arguments.duration,
            "ride_seconds": arguments.ride_seconds,
            "base_urls": arguments.base_urls,
        },
        "elapsed_seconds": round(elapsed, 1),
        "rides": dict(emulator.rides),
        "endpoints": endpoints,
    }


async def main(arguments: argparse.Namespace) -> None:
    arguments.out.mkdir(parents=True, exist_ok=True)
    connector = aiohttp.TCPConnector(limit=0)
    timeout = aiohttp.ClientTimeout(total=arguments.timeout)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        emulator = Emulator(session, arguments.base_urls, arguments.views, arguments.ride_seconds)
        stop = asyncio.Event()
        stats = asyncio.create_task(
            docker_stats(arguments.out / "stats.csv", emulator.started_at, stop, arguments.stats_interval)
        )
        try:
            await emulator.run(arguments.rps, arguments.duration)
        finally:
            stop.set()
            await stats
    elapsed = time.perf_counter() - emulator.started_at

    with (arguments.out / "requests.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("at", "endpoint", "status", "ms"))
        for sample in sorted(emulator.samples, key=lambda sample: sample.at):
            writer.writerow((f"{sample.at:.3f}", sample.endpoint, sample.status, f"{sample.seconds * 1000:.2f}"))
    summary = summarize(emulator, arguments, elapsed)
    (arguments.out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-urls", type=lambda value: value.split(","), default=["http://localhost:8000", "http://localhost:8001"])
    parser.add_argument("--rps", type=float, default=20)
    parser.add_argument("--views", type=int, default=50)
    parser.add_argument("--duration", type=float, default=120)
    parser.add_argument("--ride-seconds", type=float, default=15)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--stats-interval", type=float, default=5)
    parser.add_argument("--out", type=Path, default=Path("load/results/latest"))
    asyncio.run(main(parser.parse_args()))
