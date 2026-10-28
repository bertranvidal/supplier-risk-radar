"""Sistema de notificaciones para alertas criticas.

Envia notificaciones por Slack y/o email cuando se detectan riesgos CRITICAL.
Se ejecuta automaticamente despues del scraper.

  python3 notify.py                          # revisa las ultimas alertas y notifica
  python3 notify.py --test                   # envia una notificacion de prueba

Configuracion en .env:
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
  ALERT_EMAIL=equipo@empresa.com
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=tu@gmail.com
  SMTP_PASS=app-password
"""
from __future__ import annotations

import argparse
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from dotenv import load_dotenv

from radar.data import load_suppliers
from radar.impact import ids_of

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")


def fetch_critical_alerts() -> list[dict]:
    """Trae alertas con riesgo alto de las ultimas 24h."""
    from datetime import datetime, timedelta, timezone
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&predicted_risk=gte.0.5&scraped_at=gte.{yesterday}&order=id.desc&limit=20",
        headers=h,
    )
    if r.status_code != 200:
        return []

    sups = load_suppliers().set_index("Supplier_ID")
    alerts = []
    for row in r.json():
        title = row.get("title", "")
        summary = row.get("summary", "")
        url = row.get("url", "")
        event = row.get("predicted_event_type", "?")
        sup_ids = ids_of(row.get("predicted_supplier_ids") or "")

        text = (title + " " + summary).lower()
        stop = any(k in text for k in ["halt", "suspend", "shut", "close", "recall", "ban", "insolvency"])
        single = any(sid in sups.index and sups.loc[sid, "Single_Source"] == "Y" for sid in sup_ids)
        critical_sup = any(sid in sups.index and sups.loc[sid, "Criticality"] in ("Critical", "High") for sid in sup_ids)

        if stop and (single or critical_sup):
            priority = "CRITICAL"
        elif stop:
            priority = "HIGH"
        else:
            continue

        sup_names = []
        for sid in sup_ids:
            if sid in sups.index:
                s = sups.loc[sid]
                sup_names.append(f"{sid} {s['Supplier_Name']} ({s['Country']})")

        alerts.append({
            "priority": priority,
            "title": title,
            "summary": summary[:300],
            "url": url,
            "event": event,
            "suppliers": sup_names,
        })

    return alerts


def send_slack(alerts: list[dict]):
    """Envia alerta a Slack."""
    if not SLACK_WEBHOOK:
        print("  Slack: sin SLACK_WEBHOOK_URL configurado")
        return

    for alert in alerts:
        emoji = ":rotating_light:" if alert["priority"] == "CRITICAL" else ":warning:"
        sups = "\n".join(f"  - {s}" for s in alert["suppliers"])
        text = (
            f"{emoji} *{alert['priority']}: {alert['title']}*\n"
            f"Tipo: {alert['event']}\n"
            f"Proveedores afectados:\n{sups}\n"
            f"{alert['url']}"
        )
        r = requests.post(SLACK_WEBHOOK, json={"text": text})
        if r.status_code == 200:
            print(f"  Slack: enviado '{alert['title'][:50]}'")
        else:
            print(f"  Slack: error {r.status_code}")


def send_email(alerts: list[dict]):
    """Envia alerta por email."""
    if not ALERT_EMAIL or not SMTP_USER or not SMTP_PASS:
        print("  Email: sin configuracion SMTP completa")
        return

    for alert in alerts:
        sups = "\n".join(f"  - {s}" for s in alert["suppliers"])
        body = (
            f"ALERTA {alert['priority']}\n\n"
            f"Titular: {alert['title']}\n\n"
            f"Resumen: {alert['summary']}\n\n"
            f"Tipo de evento: {alert['event']}\n\n"
            f"Proveedores afectados:\n{sups}\n\n"
            f"Enlace: {alert['url']}\n\n"
            f"---\nSupplier Risk Radar - Helixa Pharmaceuticals"
        )

        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = f"[SUPPLIER RADAR] {alert['priority']}: {alert['title'][:60]}"
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            print(f"  Email: enviado a {ALERT_EMAIL}")
        except Exception as e:
            print(f"  Email: error {type(e).__name__}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        test_alert = [{
            "priority": "CRITICAL",
            "title": "TEST: Notificacion de prueba del Supplier Risk Radar",
            "summary": "Esta es una notificacion de prueba.",
            "url": "",
            "event": "Test",
            "suppliers": ["S001 Test Supplier (Test Country)"],
        }]
        print("Enviando notificacion de prueba...")
        send_slack(test_alert)
        send_email(test_alert)
        return

    print("Buscando alertas criticas...")
    alerts = fetch_critical_alerts()
    print(f"  {len(alerts)} alertas criticas/altas encontradas")

    if not alerts:
        print("  Sin alertas criticas. No se envia notificacion.")
        return

    send_slack(alerts)
    send_email(alerts)


if __name__ == "__main__":
    main()
