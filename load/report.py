import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE, INK, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
PERCENTILES = (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": MUTED, "axes.titlecolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.grid": True, "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left", "font.size": 9,
    "lines.linewidth": 2, "legend.frameon": False,
})


def read_requests(path: Path) -> dict[str, dict[int, list[tuple[int, float]]]]:
    by_endpoint = defaultdict(lambda: defaultdict(list))
    with path.open() as file:
        for row in csv.DictReader(file):
            by_endpoint[row["endpoint"]][int(float(row["at"]))].append((int(row["status"]), float(row["ms"])))
    return by_endpoint


def read_stats(path: Path) -> dict[str, list[tuple[float, float, float]]]:
    by_container = defaultdict(list)
    with path.open() as file:
        for row in csv.DictReader(file):
            name = row["container"].removeprefix("system-design-hw-").removesuffix("-1")
            by_container[name].append((float(row["at"]), float(row["cpu_percent"]), float(row["memory_mib"])))
    return by_container


def percentile(values: list[float], share: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * share))]


def save(figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def plot_throughput(requests, out: Path) -> None:
    reads = [endpoint for endpoint in requests if endpoint.startswith("GET")]
    writes = [endpoint for endpoint in requests if not endpoint.startswith("GET")]
    figure, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for axis, endpoints, title in ((axes[0], reads, "Чтения, запросов в секунду"), (axes[1], writes, "Записи, запросов в секунду")):
        for color, endpoint in zip(SERIES, endpoints):
            seconds = sorted(requests[endpoint])
            axis.plot(seconds, [len(requests[endpoint][second]) for second in seconds], color=color, label=endpoint)
        axis.set_title(title)
        axis.set_ylim(bottom=0)
        axis.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=3)
    axes[1].set_xlabel("секунды от начала прогона")
    save(figure, out / "throughput.png")


def plot_latency(requests, out: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11, 6.5), sharex=True)
    for axis, endpoint in zip(axes.flat, requests):
        seconds = sorted(requests[endpoint])
        for color, (name, share) in zip(SERIES, PERCENTILES):
            values = [percentile([ms for _, ms in requests[endpoint][second]], share) for second in seconds]
            axis.plot(seconds, values, color=color, label=name)
        axis.set_title(f"{endpoint}, мс")
        axis.set_ylim(bottom=0)
        axis.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=3)
    for axis in axes[1]:
        axis.set_xlabel("секунды от начала прогона")
    save(figure, out / "latency.png")


def plot_resources(stats, out: Path) -> None:
    containers = [name for name in ("rental-1", "rental-2", "postgres", "stubs") if name in stats]
    figure, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for color, name in zip(SERIES, containers):
        at, cpu, memory = zip(*stats[name])
        axes[0].plot(at, cpu, color=color, label=name)
        axes[1].plot(at, memory, color=color, label=name)
    axes[0].set_title("CPU, % одного ядра")
    axes[1].set_title("Память, МиБ")
    axes[1].set_xlabel("секунды от начала прогона")
    for axis in axes:
        axis.set_ylim(bottom=0)
        axis.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=4)
    save(figure, out / "resources.png")


def write_report(summary: dict, stats, out: Path) -> None:
    parameters = summary["parameters"]
    lines = [
        "# Нагрузочный прогон",
        "",
        f"X = {parameters['orders_rps']:g} заказов в секунду, Y = {parameters['views_per_order']} просмотров на заказ, "
        f"подача {parameters['duration_seconds']:g} с, поездка {parameters['ride_seconds']:g} с.",
        "",
        f"Поездок начато: {summary['rides'].get('started', 0)}, завершено: {summary['rides'].get('finished', 0)}, "
        f"с ошибкой: {summary['rides'].get('failed', 0)}.",
        "",
        "| Эндпоинт | Запросов | RPS | Ошибок | p50, мс | p95, мс | p99, мс | max, мс |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for endpoint, data in summary["endpoints"].items():
        latency = data["latency_ms"]
        lines.append(
            f"| `{endpoint}` | {data['requests']} | {data['rps']:g} | {data['errors']} | "
            f"{latency['p50']:g} | {latency['p95']:g} | {latency['p99']:g} | {latency['max']:g} |"
        )
    lines += ["", "| Контейнер | CPU средний, % | CPU пик, % | Память пик, МиБ |", "| --- | ---: | ---: | ---: |"]
    for name, rows in sorted(stats.items()):
        cpu, memory = [row[1] for row in rows], [row[2] for row in rows]
        lines.append(f"| {name} | {sum(cpu) / len(cpu):.0f} | {max(cpu):.0f} | {max(memory):.0f} |")
    lines += ["", "![throughput](throughput.png)", "", "![latency](latency.png)", "", "![resources](resources.png)", ""]
    (out / "report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="?", default=Path("load/results/latest"))
    results = parser.parse_args().results
    requests, stats = read_requests(results / "requests.csv"), read_stats(results / "stats.csv")
    plot_throughput(requests, results)
    plot_latency(requests, results)
    plot_resources(stats, results)
    write_report(json.loads((results / "summary.json").read_text()), stats, results)
    print(results / "report.md")
