"""Currency conversion with a provider rate and our spread."""
import requests


def rate(base, quote):
    return requests.get(f"https://fx.example/{base}{quote}", timeout=5).json()["rate"]


def convert(amount, base, quote, spread=0.01):
    return round(amount * rate(base, quote) * (1 + spread), 2)
