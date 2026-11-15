"""Run a LAN observer with an explicit config; node processes stay externally managed."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from backend.app.core.models import ClusterConfig
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Shared LAN membership JSON")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config_path = config_path.resolve()
    try:
        config = ClusterConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot load {config_path}: {exc}")
    if config.mode != "external":
        parser.error("LAN dashboard requires mode=external. Use start_demo.py for local managed nodes.")

    # Set before importing app.main, which constructs the ASGI application once.
    # This overrides an older RA_CONFIG value in this terminal intentionally.
    os.environ["RA_CONFIG"] = str(config_path)
    print(f"Config: {config_path}", flush=True)
    print(f"Session: {config.session_id} | Mode: external | Members: {len(config.nodes)}", flush=True)
    for node in config.nodes:
        print(f"  P{node.id}: {node.host}:{node.port}", flush=True)
    print(f"Dashboard port: {args.port}. Node processes are managed in their own terminals.", flush=True)
    uvicorn.run("backend.app.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
