# -*- coding: utf-8 -*-
"""
Trading-Bot – Phase 4: Paper Trading (Spielgeld-Depot)
======================================================
Führt die Strategie aus dem Backtest mit Spielgeld "live" weiter –
Tag für Tag, automatisch über GitHub Actions (siehe .github/workflows/).

Ablauf bei jedem Lauf:
 1. Letzte 200 Tageskerzen von Binance holen (öffentlich, kein Key)
 2. Nur ABGESCHLOSSENE Tage auswerten (die heutige Kerze läuft noch)
 3. Alle Tage seit dem letzten Lauf nacheinander verarbeiten –
    dadurch macht es nichts, wenn ein Lauf mal ausfällt
 4. Depot in depot.json speichern, Dashboard nach docs/index.html bauen

Aufruf: python paper_trading.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from backtest import berechne_ema, berechne_rsi

ORDNER = Path(__file__).parent
DEPOT_DATEI = ORDNER / "depot.json"
DOCS_ORDNER = ORDNER / "docs"
BASIS_URL = "https://data-api.binance.vision/api/v3/klines"
ANZAHL_KERZEN = 200   # genug Vorlauf, damit EMA und RSI eingeschwungen sind
CHART_TAGE = 180      # so viele Tage zeigt der Kurs-Chart im Dashboard


def lade_config():
    with open(ORDNER / "config.json", encoding="utf-8") as f:
        return json.load(f)


def hole_kerzen(config):
    """Holt die letzten Tageskerzen und wirft die noch laufende weg."""
    antwort = requests.get(
        BASIS_URL,
        params={
            "symbol": config["symbol"],
            "interval": config["intervall"],
            "limit": ANZAHL_KERZEN,
        },
        timeout=30,
    )
    antwort.raise_for_status()

    kerzen = [
        {
            "datum": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "close": float(k[4]),
        }
        for k in antwort.json()
    ]

    heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if kerzen and kerzen[-1]["datum"] == heute:
        kerzen.pop()  # der heutige Tag ist noch nicht zu Ende
    return kerzen


def neues_depot(config, kerzen):
    """Legt beim allerersten Lauf ein frisches Spielgeld-Depot an."""
    gebuehr = config["gebuehr_prozent"] / 100
    start = config["startkapital_euro"]
    letzte = kerzen[-1]
    return {
        "gestartet_am": letzte["datum"],
        "startkapital_euro": start,
        "bargeld": float(start),
        "coins": 0.0,
        "investiert": False,
        "letzter_kauf": None,
        # Vergleichsdepot: am Starttag alles kaufen und nie wieder anfassen
        "buyhold_coins": start * (1 - gebuehr) / letzte["close"],
        # Der Starttag selbst wird gleich unten als erster Tag verarbeitet
        "letzter_verarbeiteter_tag": kerzen[-2]["datum"],
        "erster_lauf_offen": True,
        "signale": [],
        "trades": [],
        "historie": [],
    }


def verarbeite_tage(depot, kerzen, config):
    """Geht alle noch nicht verarbeiteten, abgeschlossenen Tage durch und
    wendet die Strategie an – exakt dieselben Regeln wie im Backtest."""
    s = config["strategie"]
    gebuehr = config["gebuehr_prozent"] / 100
    kurse = [k["close"] for k in kerzen]

    ema_s = berechne_ema(kurse, s["ema_schnell"])
    ema_l = berechne_ema(kurse, s["ema_langsam"])
    rsi = berechne_rsi(kurse, s["rsi_periode"])

    erster_lauf = depot.pop("erster_lauf_offen", False)
    aktionen = []

    for i, kerze in enumerate(kerzen):
        if kerze["datum"] <= depot["letzter_verarbeiteter_tag"]:
            continue
        if ema_l[i] is None or ema_l[i - 1] is None or rsi[i] is None:
            continue

        preis = kerze["close"]
        kreuzt_hoch = ema_s[i - 1] <= ema_l[i - 1] and ema_s[i] > ema_l[i]
        kreuzt_runter = ema_s[i - 1] >= ema_l[i - 1] and ema_s[i] < ema_l[i]

        # Sonderfall allererster Tag: Läuft der Aufwärtstrend bereits, steigen
        # wir direkt ein – der Backtest wäre an diesem Punkt auch investiert.
        if erster_lauf:
            kreuzt_hoch = kreuzt_hoch or ema_s[i] > ema_l[i]
            erster_lauf = False

        if not depot["investiert"] and kreuzt_hoch and rsi[i] < s["rsi_kauf_max"]:
            depot["coins"] = depot["bargeld"] * (1 - gebuehr) / preis
            depot["letzter_kauf"] = {
                "datum": kerze["datum"],
                "preis": preis,
                "kapital_vorher": depot["bargeld"],
            }
            depot["bargeld"] = 0.0
            depot["investiert"] = True
            depot["signale"].append({"datum": kerze["datum"], "typ": "kauf", "preis": preis})
            aktionen.append(f"{kerze['datum']}: KAUF zu {preis:.2f} EUR")

        elif depot["investiert"] and kreuzt_runter:
            depot["bargeld"] = depot["coins"] * preis * (1 - gebuehr)
            depot["coins"] = 0.0
            depot["investiert"] = False
            gewinn = depot["bargeld"] - depot["letzter_kauf"]["kapital_vorher"]
            depot["trades"].append({
                "kauf_datum": depot["letzter_kauf"]["datum"],
                "kauf_preis": depot["letzter_kauf"]["preis"],
                "verkauf_datum": kerze["datum"],
                "verkauf_preis": preis,
                "gewinn_euro": round(gewinn, 2),
                "gewinn_prozent": round(gewinn / depot["letzter_kauf"]["kapital_vorher"] * 100, 2),
            })
            depot["signale"].append({"datum": kerze["datum"], "typ": "verkauf", "preis": preis})
            aktionen.append(f"{kerze['datum']}: VERKAUF zu {preis:.2f} EUR")

        wert = depot["bargeld"] if not depot["investiert"] else depot["coins"] * preis
        depot["historie"].append({
            "datum": kerze["datum"],
            "depotwert": round(wert, 2),
            "buy_hold": round(depot["buyhold_coins"] * preis, 2),
        })
        depot["letzter_verarbeiteter_tag"] = kerze["datum"]

    return aktionen, ema_s, ema_l


def erzeuge_dashboard(depot, kerzen, ema_s, ema_l, config, aktionen):
    historie = depot["historie"]
    depotwert = historie[-1]["depotwert"]
    start = depot["startkapital_euro"]

    chart_kerzen = kerzen[-CHART_TAGE:]
    versatz = len(kerzen) - len(chart_kerzen)

    daten = {
        "symbol": config["symbol"],
        "config": config,
        "stand": datetime.now(timezone.utc).strftime("%d.%m.%Y, %H:%M Uhr (UTC)"),
        "letzter_lauf": {
            "datum": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
            "zeit": datetime.now(timezone.utc).strftime("%H:%M UTC"),
            "aktion": aktionen[-1] if aktionen else "kein Signal – Bot wartet",
        },
        "gestartet_am": depot["gestartet_am"],
        "kennzahlen": {
            "depotwert": depotwert,
            "startkapital": start,
            "rendite_prozent": round((depotwert / start - 1) * 100, 2),
            "buy_hold_prozent": round((historie[-1]["buy_hold"] / start - 1) * 100, 2),
            "investiert": depot["investiert"],
            "anzahl_trades": len(depot["trades"]),
            "einstieg": depot["letzter_kauf"] if depot["investiert"] else None,
        },
        "historie": historie,
        "chart_daten": [k["datum"] for k in chart_kerzen],
        "chart_kurse": [k["close"] for k in chart_kerzen],
        "chart_ema_schnell": ema_s[versatz:],
        "chart_ema_langsam": ema_l[versatz:],
        "signale": depot["signale"],
        "trades": depot["trades"],
    }

    with open(ORDNER / "paper_vorlage.html", encoding="utf-8") as f:
        vorlage = f.read()
    html = vorlage.replace("/*__DATEN__*/null", json.dumps(daten, ensure_ascii=False))

    DOCS_ORDNER.mkdir(exist_ok=True)
    ziel = DOCS_ORDNER / "index.html"
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(html)
    return ziel


def main():
    config = lade_config()
    kerzen = hole_kerzen(config)

    if DEPOT_DATEI.exists():
        with open(DEPOT_DATEI, encoding="utf-8") as f:
            depot = json.load(f)
    else:
        print("Erster Lauf – lege neues Spielgeld-Depot an.")
        depot = neues_depot(config, kerzen)

    aktionen, ema_s, ema_l = verarbeite_tage(depot, kerzen, config)

    with open(DEPOT_DATEI, "w", encoding="utf-8") as f:
        json.dump(depot, f, ensure_ascii=False, indent=2)

    ziel = erzeuge_dashboard(depot, kerzen, ema_s, ema_l, config, aktionen)

    letzter = depot["historie"][-1]
    status = "investiert" if depot["investiert"] else "in Bargeld"
    print(f"Stand {letzter['datum']}: Depotwert {letzter['depotwert']:.2f} EUR ({status})")
    if aktionen:
        for a in aktionen:
            print("  " + a)
    else:
        print("  Keine neuen Signale.")
    print(f"Dashboard aktualisiert: {ziel}")


if __name__ == "__main__":
    main()
