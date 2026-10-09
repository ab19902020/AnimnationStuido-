"""python3 -m studio.web [--port 8000] [--host 127.0.0.1]: the web studio (see studio/web/__init__.py)"""
import argparse
import os

from studio.paths import ROOT
from studio.web.server import serve

ap = argparse.ArgumentParser(description="The Animation Studio in the browser")
ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to let other machines on the network in")
ap.add_argument("--port", type=int, default=8000)
a = ap.parse_args()
os.chdir(ROOT)
serve(a.host, a.port)
