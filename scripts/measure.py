#!/usr/bin/env python3


from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


OPS = [
    ("GET", "/api/loans?page=1&size=20"),
    ("GET", "/api/loans?page=1&size=20&status=overdue"),
    ("GET", "/api/loans?page=1&size=20&q=книга"),
    ("GET", "/api/loans/1"),
    ("GET", "/api/summary"),
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def measure(client: httpx.Client, method: str, path: str, repeats: int, warmup: int) -> dict:
    totals: list[float] = []
    db_times: list[float] = []
    app_times: list[float] = []
    query_counts: list[int] = []

    for i in range(warmup + repeats):
        started = time.perf_counter()
        response = client.request(method, path, headers={"X-Measure": "1"})
        client_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        if i < warmup:
            continue

        total_ms = float(response.headers.get("X-Total-Ms", client_ms))
        db_ms = float(response.headers.get("X-Db-Ms", "0"))
        app_ms = float(response.headers.get("X-App-Ms", max(total_ms - db_ms, 0)))
        db_n = int(response.headers.get("X-Db-Queries", "0"))

        totals.append(total_ms)
        db_times.append(db_ms)
        app_times.append(app_ms)
        query_counts.append(db_n)

    return {
        "path": f"{method} {path}",
        "median_ms": round(statistics.median(totals), 2),
        "p95_ms": round(percentile(totals, 0.95), 2),
        "max_ms": round(max(totals), 2),
        "db_median_ms": round(statistics.median(db_times), 2),
        "app_median_ms": round(statistics.median(app_times), 2),
        "queries_median": round(statistics.median(query_counts), 1),
        "n": len(totals),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--user", default="demo")
    parser.add_argument("--password", default="demo")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--volume-label", default="unknown")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=300.0) as client:
        login = client.post("/api/auth/login", json={"username": args.user, "password": args.password})
        login.raise_for_status()
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"

        rows = []
        print(
            f"volume={args.volume_label} account={args.user} "
            f"repeats={args.repeats} warmup={args.warmup}"
        )
        print(
            f"{'operation':<42} {'p50':>8} {'p95':>8} {'max':>8} "
            f"{'db':>8} {'app':>8} {'q':>5}"
        )
        for method, path in OPS:
            row = measure(client, method, path, args.repeats, args.warmup)
            rows.append(row)
            print(
                f"{row['path']:<42} {row['median_ms']:>8.2f} {row['p95_ms']:>8.2f} "
                f"{row['max_ms']:>8.2f} {row['db_median_ms']:>8.2f} "
                f"{row['app_median_ms']:>8.2f} {row['queries_median']:>5.1f}"
            )

    payload = {
        "volume": args.volume_label,
        "account": args.user,
        "repeats": args.repeats,
        "warmup": args.warmup,
        "operations": rows,
    }
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved {out_path}")


if __name__ == "__main__":
    main()
