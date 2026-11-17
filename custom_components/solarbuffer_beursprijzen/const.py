"""Vaste waarden voor SolarBuffer Beursprijzen."""

from datetime import timedelta

DOMAIN = "solarbuffer_beursprijzen"
API_URL = "https://hub.solarbuffer.nl/v1/energieprijzen"

CONF_LEVERANCIER = "leverancier"
# Wie alleen de kale beursprijs wil, zonder opslag van een leverancier.
ALLEEN_BEURS = "__beurs__"

# De prijzen staan uren vooruit vast, dus een keer per uur ophalen is genoeg.
# De prijzen van morgen komen rond 13:00; tot ze binnen zijn kijken we tussen
# 13:00 en 15:00 elk kwartier. De stand van "nu" rekenen we zelf elk heel uur
# bij, daar is geen verzoek voor nodig.
UPDATE_INTERVAL = timedelta(hours=1)
SNEL_INTERVAL = timedelta(minutes=15)
SNEL_VAN_UUR = 13
SNEL_TOT_UUR = 15
