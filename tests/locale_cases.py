"""One locale case list shared by the core, HTTP and Action boundary tests.

Every host must accept and normalize exactly these values and reject the rest.
"""

#: (supplied value, canonical locale identifier)
ACCEPTED = [
    ("en", "en"),
    ("EN", "en"),
    ("pt-br", "pt-br"),
    ("pt_br", "pt-br"),
    ("PT-BR", "pt-br"),
    ("pt_BR", "pt-br"),
]

REJECTED = [
    "",
    "es",
    "pt",
    "pt-pt",
    "en-us",
    "../../docs/criteria_example",
    "../en",
    "en/../en",
    "./en",
    "en.json",
    "/etc/passwd",
    " en",
    "en ",
    "e\x00n",
    "x" * 33,
]
