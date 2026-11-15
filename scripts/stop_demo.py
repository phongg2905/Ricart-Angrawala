"""Stops locally managed nodes. Ctrl+C in the launcher also stops the web server."""
import argparse
import json
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000")
args = parser.parse_args()
with urlopen(Request(args.url.rstrip("/") + "/api/simulation/stop", method="POST"), timeout=30) as response:
    print(json.loads(response.read())["status"])
