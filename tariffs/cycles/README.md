# ERSE period tables (Portugal continental, BTN, ciclo diário)

Encoded in `portinhola/core/cycles.py`. The daily cycle applies the same
schedule every day of the year; periods follow legal (clock) time, so the
winter/summer split tracks the DST switch.

- Bi-horário: Vazio 22:00–08:00, Fora de Vazio 08:00–22:00.
- Tri-horário, hora legal de inverno: Ponta 09:00–10:30 and 18:00–20:30;
  Cheias 08:00–09:00, 10:30–18:00, 20:30–22:00; Vazio 22:00–08:00.
- Tri-horário, hora legal de verão: Ponta 10:30–13:00 and 19:30–21:00;
  Cheias 08:00–10:30, 13:00–19:30, 21:00–22:00; Vazio 22:00–08:00.

Sources (retrieved 2026-07-28):
- ERSE, "Períodos horários de energia elétrica em Portugal" —
  https://www.erse.pt/media/wijn0vgt/periodos-hor%C3%A1rios-de-energia-el%C3%A9trica-em-portugal.pdf
- Reference tables cross-checked at
  https://www.tiagofelicia.pt/periodos-horarios.html

Note: ERSE consultation CP137 (Nov 2025) proposes shifting these periods
(e.g. vazio 23:00–09:00). Not in force at the time of writing — update this
file and `cycles.py` together when it lands.

Ciclo semanal is not yet implemented (household contracts overwhelmingly
use ciclo diário); the mapper raises a clear error for it.
