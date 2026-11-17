"""Vaste waarden voor SolarBuffer Beursprijzen."""

from datetime import timedelta

DOMAIN = "solarbuffer_beursprijzen"
API_URL = "https://hub.solarbuffer.nl/v1/energieprijzen"

CONF_LEVERANCIER = "leverancier"
# Wie alleen de kale beursprijs wil, zonder opslag van een leverancier.
ALLEEN_BEURS = "__beurs__"

# De server ververst de beursprijzen een paar keer per dag. Elk kwartier
# kijken is ruim genoeg; de stand van "nu" rekenen we zelf elk heel uur bij.
UPDATE_INTERVAL = timedelta(minutes=15)
