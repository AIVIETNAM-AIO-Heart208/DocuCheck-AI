"""Opt-in actual web inference measurement. Never invoked by setup or startup."""

import argparse
import json
from pathlib import Path
import time
import uuid


def main():
    import httpx
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-inference", action="store_true", required=True)
    parser.add_argument("--jobs", type=int, default=6, help="First job is cold, at least five later jobs")
    args = parser.parse_args()
    if args.jobs < 6 or args.output.exists():
        raise ValueError("Choose >=6 jobs and a new output file")
    if len(args.images) < 2:
        raise ValueError("Choose at least two different images")
    records = []
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        response = client.get("/api/session")
        response.raise_for_status()
        for i in range(args.jobs):
            image = args.images[i % len(args.images)]
            started = time.perf_counter()
            with image.open("rb") as stream:
                response = client.post("/api/jobs", files={"file":(image.name,stream)},
                                       headers={"Idempotency-Key":uuid.uuid4().hex})
            response.raise_for_status()
            key = response.json()["job_id"]
            deadline = time.monotonic()+900
            while True:
                response = client.get(f"/api/jobs/{key}")
                response.raise_for_status()
                body = response.json()
                if body["state"] in {"succeeded","partial","failed","cancelled"}:
                    break
                if time.monotonic() >= deadline:
                    client.post(f"/api/jobs/{key}/cancel")
                    raise TimeoutError("Benchmark stopped; cancellation requested")
                time.sleep(1)
            records.append({"index":i, "kind":"cold_candidate" if i == 0 else "subsequent",
                            "image":image.name, "job_id":key, "state":body["state"],
                            "client_seconds":time.perf_counter()-started, "timing":body.get("timing"),
                            "load_count":body.get("model_load_count"), "gpu_policy":body["gpu_policy"],
                            "resource_samples":body.get("resource_samples"), "job_load_count":body.get("job_load_count"),
                            "error":body.get("error")})
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps({"note":"Cold only if server had no prior jobs; no accuracy score",
                                              "jobs":records},ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
