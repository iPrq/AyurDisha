"""Official domains web search is restricted to, per legal_scope (Indian vs international)."""

from __future__ import annotations

INDIA_REGULATOR_DOMAINS = [
    "ayush.gov.in",
    "cdsco.gov.in",
    "fssai.gov.in",
    "indiacode.nic.in",
    "egazette.gov.in",
]

INTERNATIONAL_REGULATOR_DOMAINS = [
    "who.int",
    "fda.gov",
    "ema.europa.eu",
    "efsa.europa.eu",
    "eur-lex.europa.eu",
    "gov.uk",
    "tga.gov.au",
    "canada.ca",
]

INTERNATIONAL_IP_DOMAINS = [
    "wipo.int",
    "epo.org",
    "uspto.gov",
    "patents.google.com",
]
