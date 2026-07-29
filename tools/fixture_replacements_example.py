"""Template for tools/fixture_replacements_local.py (gitignored).

Copy this file to `fixture_replacements_local.py` and replace the left-hand
patterns with the REAL values printed on your bills. Everything a stranger
could use to identify you or your supply must be mapped: name, NIF, email,
address, postal code, CPE/CUI, meter serials, client/contract numbers,
document numbers, ATCUD codes and payment references.
"""

REPLACEMENTS: list[tuple[str, str]] = [
    (r"Your Full Name Here", "Maria Exemplo Silva"),
    (r"YOUR FULL NAME HERE", "MARIA EXEMPLO SILVA"),
    (r"123456789", "299999998"),  # your NIF
    (r"you@example\.org", "maria@example.com"),
    (r"Rua Da Sua Casa[^\n]*", "Rua Exemplo, 1"),
    (r"0000-000 LOCALIDADE", "4000-000 CIDADE"),
    (r"PT0002\d{12}[A-Z]{2}", "PT0002000000000000XX"),  # electricity CPE
    (r"PT1601\d{12}[A-Z]{2}", "PT1601000000000000XX"),  # gas CUI
    (r"PT50[\d*]{18,}", "PT50000000000000000000000"),  # IBAN
    (r"Mandato: \d+", "Mandato: 10000000000"),
]
