# -*- coding: utf-8 -*-
"""
Trading-Bot – Phase 1: Historische Kursdaten laden
==================================================
Holt Tageskerzen (Open/High/Low/Close/Volumen) von der öffentlichen
Binance-Daten-API. Dafür ist KEIN Account und KEIN API-Key nötig,
weil es reine Marktdaten sind.

Aufruf:   python daten_laden.py
Ergebnis: daten/BTCEUR_1d.json
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Öffentlicher Marktdaten-Endpunkt von Binance (nur Lesen, kein Key nötig)
BASIS_URL = "https://data-api.binance.vision/api/v3/klines"

ORDNER = Path(__file__).parent
DATEN_ORDNER = ORDNER / "daten"


def lade_config():
    with open(ORDNER / "config.json", encoding="utf-8") as f:
        return json.load(f)


def lade_kerzen(symbol, intervall, start_ms):
    """Holt alle Kerzen ab start_ms. Binance liefert max. 1000 Stück
    pro Anfrage, deshalb fragen wir in einer Schleife nach, bis wir
    in der Gegenwart angekommen sind."""
    alle_kerzen = []

    while True:
        antwort = requests.get(
            BASIS_URL,
            params={
                "symbol": symbol,
                "interval": intervall,
                "startTime": start_ms,
                "limit": 1000,
            },
            timeout=30,
        )
        antwort.raise_for_status()
        kerzen = antwort.json()

        if not kerzen:
            break

        alle_kerzen.extend(kerzen)
        print(f"  {len(alle_kerzen)} Kerzen geladen ...")

        if len(kerzen) < 1000:
            break  # weniger als 1000 zurück = wir sind am aktuellen Rand

        # Nächste Anfrage startet direkt nach der letzten Kerze
        start_ms = kerzen[-1][0] + 1
        time.sleep(0.3)  # kleine Pause, um die API nicht zu ärgern

    return alle_kerzen


def main():
    config = lade_config()
    symbol = config["symbol"]
    intervall = config["intervall"]

    start = datetime.strptime(config["start_datum"], "%Y-%m-%d")
    start_ms = int(start.replace(tzinfo=timezone.utc).timestamp() * 1000)

    print(f"Lade {symbol} ({intervall}-Kerzen) ab {config['start_datum']} ...")
    rohdaten = lade_kerzen(symbol, intervall, start_ms)

    # Binance liefert Listen – wir machen daraus lesbare Objekte
    kerzen = []
    for k in rohdaten:
        kerzen.append({
            "datum": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volumen": float(k[5]),
        })

    DATEN_ORDNER.mkdir(exist_ok=True)
    ziel = DATEN_ORDNER / f"{symbol}_{intervall}.json"
    with open(ziel, "w", encoding="utf-8") as f:
        json.dump(kerzen, f, ensure_ascii=False, indent=2)

    print(f"\nFertig! {len(kerzen)} Kerzen gespeichert in: {ziel}")
    print(f"Zeitraum: {kerzen[0]['datum']} bis {kerzen[-1]['datum']}")


if __name__ == "__main__":
    main()
