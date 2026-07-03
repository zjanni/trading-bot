# -*- coding: utf-8 -*-
"""
Trading-Bot – Phase 2: Backtest
===============================
Spielt eine Strategie auf den historischen Daten durch, als hätte
man sie in der Vergangenheit wirklich gehandelt.

Die Strategie (bewusst einfach gehalten):
  KAUFEN,    wenn der schnelle EMA über den langsamen EMA kreuzt
             (Aufwärtstrend beginnt) UND der RSI nicht überhitzt ist.
  VERKAUFEN, wenn der schnelle EMA wieder unter den langsamen fällt.

Es wird immer das komplette Kapital eingesetzt, Gebühren werden bei
jedem Kauf und Verkauf abgezogen. Zum Vergleich rechnen wir aus,
was "einfach am Anfang kaufen und liegen lassen" gebracht hätte
(Buy & Hold) – das ist die Messlatte, die eine Strategie schlagen muss.

Aufruf:   python backtest.py
Ergebnis: dashboard.html  (im Browser öffnen)
"""

import json
from pathlib import Path

ORDNER = Path(__file__).parent


# ---------------------------------------------------------------
# Indikatoren
# ---------------------------------------------------------------

def berechne_ema(kurse, periode):
    """Exponentieller gleitender Durchschnitt.
    Reagiert schneller auf neue Kurse als ein normaler Durchschnitt."""
    ema = [None] * len(kurse)
    faktor = 2 / (periode + 1)
    # Startwert: einfacher Durchschnitt der ersten `periode` Kurse
    ema[periode - 1] = sum(kurse[:periode]) / periode
    for i in range(periode, len(kurse)):
        ema[i] = kurse[i] * faktor + ema[i - 1] * (1 - faktor)
    return ema


def berechne_rsi(kurse, periode):
    """Relative-Stärke-Index (0–100). Über ~70 gilt der Markt als
    'überkauft' – dann kaufen wir lieber nicht mehr hinterher."""
    rsi = [None] * len(kurse)
    gewinne, verluste = 0.0, 0.0

    for i in range(1, periode + 1):
        diff = kurse[i] - kurse[i - 1]
        if diff >= 0:
            gewinne += diff
        else:
            verluste -= diff

    avg_gewinn = gewinne / periode
    avg_verlust = verluste / periode

    for i in range(periode, len(kurse)):
        if i > periode:
            diff = kurse[i] - kurse[i - 1]
            gewinn = max(diff, 0)
            verlust = max(-diff, 0)
            # Wilder-Glättung: alte Werte klingen langsam ab
            avg_gewinn = (avg_gewinn * (periode - 1) + gewinn) / periode
            avg_verlust = (avg_verlust * (periode - 1) + verlust) / periode

        if avg_verlust == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gewinn / avg_verlust
            rsi[i] = 100 - 100 / (1 + rs)

    return rsi


# ---------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------

def backtest(kerzen, config):
    s = config["strategie"]
    kurse = [k["close"] for k in kerzen]

    ema_schnell = berechne_ema(kurse, s["ema_schnell"])
    ema_langsam = berechne_ema(kurse, s["ema_langsam"])
    rsi = berechne_rsi(kurse, s["rsi_periode"])

    kapital = config["startkapital_euro"]
    gebuehr = config["gebuehr_prozent"] / 100
    coins = 0.0            # wie viel BTC wir gerade halten
    investiert = False

    trades = []            # abgeschlossene Kauf/Verkauf-Paare
    kauf_signale = []      # für die Marker im Chart
    verkauf_signale = []
    equity = []            # Kapitalverlauf der Strategie
    letzter_kauf = None

    for i, kerze in enumerate(kerzen):
        preis = kerze["close"]

        # Erst handeln, wenn alle Indikatoren Werte haben
        if ema_langsam[i] is not None and ema_langsam[i - 1] is not None and rsi[i] is not None:
            kreuzt_hoch = ema_schnell[i - 1] <= ema_langsam[i - 1] and ema_schnell[i] > ema_langsam[i]
            kreuzt_runter = ema_schnell[i - 1] >= ema_langsam[i - 1] and ema_schnell[i] < ema_langsam[i]

            if not investiert and kreuzt_hoch and rsi[i] < s["rsi_kauf_max"]:
                coins = kapital * (1 - gebuehr) / preis
                letzter_kauf = {"datum": kerze["datum"], "preis": preis, "kapital_vorher": kapital}
                kapital = 0.0
                investiert = True
                kauf_signale.append({"datum": kerze["datum"], "preis": preis})

            elif investiert and kreuzt_runter:
                kapital = coins * preis * (1 - gebuehr)
                coins = 0.0
                investiert = False
                verkauf_signale.append({"datum": kerze["datum"], "preis": preis})
                gewinn = kapital - letzter_kauf["kapital_vorher"]
                trades.append({
                    "kauf_datum": letzter_kauf["datum"],
                    "kauf_preis": letzter_kauf["preis"],
                    "verkauf_datum": kerze["datum"],
                    "verkauf_preis": preis,
                    "gewinn_euro": round(gewinn, 2),
                    "gewinn_prozent": round(gewinn / letzter_kauf["kapital_vorher"] * 100, 2),
                })

        # Depotwert an diesem Tag (Bargeld oder Coins zum Tageskurs)
        wert = kapital if not investiert else coins * preis
        equity.append(round(wert, 2))

    # Falls am Ende noch investiert: zum letzten Kurs bewerten (offene Position)
    endkapital = equity[-1]

    # Vergleich: Buy & Hold (am ersten Tag kaufen, nie verkaufen)
    bh_coins = config["startkapital_euro"] * (1 - gebuehr) / kurse[0]
    buy_hold = [round(bh_coins * p, 2) for p in kurse]

    return {
        "ema_schnell": ema_schnell,
        "ema_langsam": ema_langsam,
        "rsi": rsi,
        "trades": trades,
        "kauf_signale": kauf_signale,
        "verkauf_signale": verkauf_signale,
        "equity": equity,
        "buy_hold": buy_hold,
        "endkapital": endkapital,
        "noch_investiert": investiert,
    }


def berechne_kennzahlen(ergebnis, config):
    start = config["startkapital_euro"]
    trades = ergebnis["trades"]
    gewinner = [t for t in trades if t["gewinn_euro"] > 0]

    # Maximaler Drawdown: größter Verlust vom bisherigen Höchststand aus
    hoechststand = 0.0
    max_drawdown = 0.0
    for wert in ergebnis["equity"]:
        hoechststand = max(hoechststand, wert)
        if hoechststand > 0:
            max_drawdown = max(max_drawdown, (hoechststand - wert) / hoechststand)

    return {
        "startkapital": start,
        "endkapital": round(ergebnis["endkapital"], 2),
        "rendite_prozent": round((ergebnis["endkapital"] / start - 1) * 100, 2),
        "buy_hold_prozent": round((ergebnis["buy_hold"][-1] / start - 1) * 100, 2),
        "anzahl_trades": len(trades),
        "trefferquote_prozent": round(len(gewinner) / len(trades) * 100, 1) if trades else 0,
        "max_drawdown_prozent": round(max_drawdown * 100, 2),
        "noch_investiert": ergebnis["noch_investiert"],
    }


# ---------------------------------------------------------------
# Dashboard erzeugen
# ---------------------------------------------------------------

def erzeuge_dashboard(kerzen, ergebnis, kennzahlen, config):
    daten_fuer_js = {
        "symbol": config["symbol"],
        "config": config,
        "daten": [k["datum"] for k in kerzen],
        "kurse": [k["close"] for k in kerzen],
        "ema_schnell": ergebnis["ema_schnell"],
        "ema_langsam": ergebnis["ema_langsam"],
        "rsi": ergebnis["rsi"],
        "equity": ergebnis["equity"],
        "buy_hold": ergebnis["buy_hold"],
        "kauf_signale": ergebnis["kauf_signale"],
        "verkauf_signale": ergebnis["verkauf_signale"],
        "trades": ergebnis["trades"],
        "kennzahlen": kennzahlen,
    }

    with open(ORDNER / "dashboard_vorlage.html", encoding="utf-8") as f:
        vorlage = f.read()

    html = vorlage.replace("/*__DATEN__*/null", json.dumps(daten_fuer_js, ensure_ascii=False))

    ziel = ORDNER / "dashboard.html"
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(html)

    # Kopie für die GitHub-Pages-Seite (dort verlinkt das Paper-Trading darauf)
    docs = ORDNER / "docs"
    docs.mkdir(exist_ok=True)
    with open(docs / "backtest.html", "w", encoding="utf-8") as f:
        f.write(html)

    return ziel


def main():
    with open(ORDNER / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    daten_datei = ORDNER / "daten" / f"{config['symbol']}_{config['intervall']}.json"
    if not daten_datei.exists():
        print("Keine Daten gefunden – bitte zuerst ausführen:  python daten_laden.py")
        return

    with open(daten_datei, encoding="utf-8") as f:
        kerzen = json.load(f)

    print(f"Backtest: {config['symbol']}, {kerzen[0]['datum']} bis {kerzen[-1]['datum']}, "
          f"Startkapital {config['startkapital_euro']} €")

    ergebnis = backtest(kerzen, config)
    kennzahlen = berechne_kennzahlen(ergebnis, config)

    print()
    print(f"  Endkapital:        {kennzahlen['endkapital']:>10.2f} €")
    print(f"  Rendite Strategie: {kennzahlen['rendite_prozent']:>10.2f} %")
    print(f"  Rendite Buy&Hold:  {kennzahlen['buy_hold_prozent']:>10.2f} %")
    print(f"  Trades:            {kennzahlen['anzahl_trades']:>10}")
    print(f"  Trefferquote:      {kennzahlen['trefferquote_prozent']:>10.1f} %")
    print(f"  Max. Drawdown:     {kennzahlen['max_drawdown_prozent']:>10.2f} %")
    if kennzahlen["noch_investiert"]:
        print("  (Position am Ende noch offen – zum letzten Kurs bewertet)")

    ziel = erzeuge_dashboard(kerzen, ergebnis, kennzahlen, config)
    print(f"\nDashboard erzeugt: {ziel}")
    print("Einfach doppelklicken oder im Browser öffnen.")


if __name__ == "__main__":
    main()
