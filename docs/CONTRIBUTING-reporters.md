# Contributing a reading-submission reporter

Reporters automate "comunicar leitura" on a comercializador's portal.
Every Portuguese supplier has its own portal (or IVR line), so each gets
one small Python module — same contribution pattern as bill extractors.

## The interface

Create `portinhola/reporters/<supplier>.py`:

```python
from portinhola.reporters.base import Confirmation, Reporter, register


@register
class MySupplierReporter(Reporter):
    name = "mysupplier"
    version = "1"
    supplier_nifs = frozenset({"500000000"})
    assisted = False  # True if the portal has a CAPTCHA (see below)

    def submit(self, readings: dict[str, float], contract) -> Confirmation:
        # Drive the portal with Playwright: log in with the stored
        # credentials/session, enter each register's value, submit, and
        # return the confirmation reference the portal shows.
        ...
```

`readings` maps register name → value (e.g. `{"Total": 3384.0}` for gas,
`{"Vazio": ..., "Cheias": ..., "Ponta": ...}` for electricity).

Guidelines:

- Keep ALL portal-specific selectors/URLs in your module — a portal change
  must be a one-file fix.
- Separate navigation from any response parsing so parsing is testable
  with saved HTML fixtures (live portals can't run in CI).
- On failure raise; the framework marks the readings `needs_manual` and
  shows the contract's manual guidance (portal link / IVR phone +
  reference), so a broken module degrades gracefully.
- Portals behind CAPTCHA set `assisted = True`: the submission then runs
  through the same streamed-browser flow as the E-Redes login, with the
  user solving the CAPTCHA (framework support for assisted submission
  lands with the first such module).
- Never commit credentials, references, or fixture data containing
  personal information.

Known targets waiting for a module: G9 (`my.g9.pt`, NIF 504435302) and
Águas de Valongo / Be Water (NIF 505084040 — also has an IVR line, which
the manual guidance card already covers).
