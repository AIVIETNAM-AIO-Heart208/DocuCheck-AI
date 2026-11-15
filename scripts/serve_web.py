"""Start the local API only when explicitly invoked. No development reload."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    from dotenv import load_dotenv
    import uvicorn
    load_dotenv(args.env_file, override=False)
    from docucheck.web.ipc import configure_stdio, worker_environment
    configure_stdio()
    os.environ.update(worker_environment(dict(os.environ)))
    os.environ["PYTHONPATH"] = str(ROOT / "src")
    uvicorn.run("docucheck.web.api:create_app", factory=True, host=args.host,
                port=args.port, workers=1, access_log=False, timeout_graceful_shutdown=120)


if __name__ == "__main__":
    main()
