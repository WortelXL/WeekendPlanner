# 🏕️ Familie Weekendplanner

Een kleine webapp om familie-uitjes te plannen: planning per dag, locatie (met kaart en route) en gegevens (contactpersonen, kosten, inpaklijst, …). Afgeschermd met pincodes per rol.

## Starten

```bash
docker compose up -d --build
```

Open daarna `http://<ip-van-je-server>/` en log in met de admin-pincode **1234** (of wat je bij `ADMIN_PIN` hebt ingevuld).
Wijzig deze pincode direct via **⚙️ Instellingen**.

Alle gegevens staan in `./data` (SQLite-database + sessiesleutel). Maak daar af en toe een back-up van.

## Rollen

| Rol      | Mag                                                                 |
|----------|---------------------------------------------------------------------|
| admin    | Alles: uitjes aanmaken/verwijderen, pincodes en beveiliging beheren |
| planner  | Uitjes bewerken: planning, locatie, contactpersonen, gegevens       |
| lezer    | Alleen inzien                                                       |

Elke rol heeft een eigen pincode (4–8 cijfers). De pincode bepaalt de rol, dus ze moeten verschillend zijn.
Planner- en lezer-pincodes stel je als admin in onder Instellingen; je kunt ze ook uitschakelen.
Wijzig je een pincode, dan worden ingelogde gebruikers met die rol automatisch uitgelogd.

## Beveiliging

- Na **5 foute pogingen** wordt de pincode-invoer **10 minuten** vergrendeld (per IP-adres/apparaat). Beide waarden zijn als admin aan te passen.
- De admin ziet actieve vergrendelingen en kan ze direct vrijgeven.
- Pincodes worden gehasht opgeslagen (scrypt).
- Sessies verlopen na 12 uur (`SESSION_HOURS`).

## Instellingen (omgevingsvariabelen)

| Variabele      | Standaard | Uitleg |
|----------------|-----------|--------|
| `ADMIN_PIN`    | `1234`    | Start-pincode admin, alleen bij eerste start |
| `BEHIND_PROXY` | `0`       | `1` achter een reverse proxy (leest `X-Forwarded-For`) |
| `COOKIE_SECURE`| `0`       | `1` als je via HTTPS werkt |
| `SESSION_HOURS`| `12`      | Hoe lang je ingelogd blijft |
| `SECRET_KEY`   | (auto)    | Wordt anders automatisch aangemaakt in `./data` |

## Admin-pincode vergeten?

```bash
docker compose down
rm data/weekend.db-wal data/weekend.db-shm 2>/dev/null
sqlite3 data/weekend.db "DELETE FROM settings WHERE key='pin_admin';"
docker compose up -d
```
De admin-pincode is daarna weer de waarde van `ADMIN_PIN`. (Heb je geen `sqlite3`: `docker run --rm -v $PWD/data:/data keinos/sqlite3 sqlite3 /data/weekend.db "DELETE FROM settings WHERE key='pin_admin';"`)

> Tip: zet de app niet rechtstreeks open op internet zonder HTTPS. Gebruik bijvoorbeeld een reverse proxy met een certificaat of een VPN (Tailscale/WireGuard).
