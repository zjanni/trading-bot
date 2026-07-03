# Trading-Bot (Krypto-Backtest)

Testet eine einfache Handelsstrategie auf historischen Bitcoin-Kursen –
ohne echtes Geld, ohne Account, ohne API-Key.

## Benutzung (2 Schritte)

```
python daten_laden.py    # holt aktuelle Kursdaten von Binance
python backtest.py       # rechnet die Strategie durch und erzeugt dashboard.html
```

Danach `dashboard.html` im Browser öffnen (Doppelklick).

## Die Strategie

- **Kaufen**, wenn der schnelle EMA (12 Tage) über den langsamen EMA (26 Tage)
  kreuzt und der RSI unter 70 liegt (Markt nicht überhitzt).
- **Verkaufen**, wenn der schnelle EMA wieder unter den langsamen fällt.
- Bei jedem Kauf/Verkauf werden 0,1 % Gebühren abgezogen.

Alle Stellschrauben stehen in `config.json` – einfach ändern und
`backtest.py` neu laufen lassen:

| Einstellung          | Bedeutung                                    |
|----------------------|----------------------------------------------|
| `symbol`             | Handelspaar, z.B. `BTCEUR`, `ETHEUR`         |
| `start_datum`        | Ab wann getestet wird                        |
| `startkapital_euro`  | Simuliertes Startkapital                     |
| `gebuehr_prozent`    | Gebühr pro Kauf/Verkauf                      |
| `ema_schnell/langsam`| Perioden der gleitenden Durchschnitte        |
| `rsi_kauf_max`       | Kein Kauf, wenn RSI darüber liegt            |

Achtung: Nach einem Symbol-Wechsel einmal `daten_laden.py` neu ausführen.

## Phase 4: Paper Trading (läuft automatisch)

Der Bot führt die Strategie täglich mit **Spielgeld** weiter. Ein
GitHub-Actions-Workflow (`.github/workflows/paper-trading.yml`) läuft
jeden Morgen, holt den letzten Tagesschlusskurs, entscheidet nach den
gleichen Regeln wie der Backtest und speichert alles im Repo:

- `depot.json` – das aktuelle Spielgeld-Depot (Bargeld, Coins, Trades)
- `docs/index.html` – das Paper-Trading-Dashboard (via GitHub Pages
  auch vom Handy erreichbar)

Manuell anstoßen: GitHub → Actions → „Paper-Trading" → „Run workflow".
Lokal testen: `python paper_trading.py`

## Dateien

- `daten_laden.py` – Phase 1: Kursdaten von Binance laden
- `backtest.py` – Phase 2+3: Backtest rechnen, Dashboard erzeugen
- `paper_trading.py` – Phase 4: tägliches Paper Trading
- `dashboard_vorlage.html` / `paper_vorlage.html` – Design-Vorlagen (nicht direkt öffnen)
- `dashboard.html` – Backtest-Ergebnis (lokal)
- `docs/` – veröffentlichte Dashboards (GitHub Pages)
- `depot.json` – Spielgeld-Depot des Paper-Tradings
- `daten/` – heruntergeladene Kursdaten (lokal)

## Wichtig

Ein Backtest zeigt nur die Vergangenheit. Gute Backtest-Zahlen sind
**keine** Garantie für die Zukunft. Nächster sinnvoller Schritt wäre
Paper Trading (simuliertes Live-Handeln) – erst ganz am Ende, wenn
überhaupt, echtes Geld.
