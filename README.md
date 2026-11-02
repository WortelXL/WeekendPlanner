# 🏕️ Familie Weekendplanner

**Versie 0.0.8** · zie [CHANGELOG.md](CHANGELOG.md)

Een kleine webapp om familie-uitjes te plannen: planning per dag, locatie (met kaart en route) en gegevens (contactpersonen, kosten, inpaklijst, …). Afgeschermd met pincodes per rol.

## Functies

- **Uitje kiezen** na het invoeren van de pincode, met filter op status:
  - 📝 **Concept**: nog in voorbereiding
  - 📅 **Gepland**: het gaat door
  - 🟢 **Gaande**: we zijn nu onderweg (staat bovenaan en opent direct de dagplanning van vandaag)
- Per uitje zes vaste tabbladen:
  - **Planning**: overzicht van alle dagen
  - **Dagplanning**: per dag een eigen sub-tabblad (Dag 1, Dag 2, …) met thema, notities en een tijdlijn; wat nu bezig is wordt gemarkeerd
  - **Locatie**: adres, kaart, route en praktische info
  - **Gegevens**: contactpersonen en overige info
  - **Aanwezig**: wie er komen, met bijzonderheden per persoon
  - **Bijlagen**: foto's, PDF's en andere bestanden uploaden en bekijken, plus links (websites) met een eigen naam
- **Klikbare links**: webadressen in tekstvelden worden vanzelf klikbaar; eigen linktekst met `[tekst](https://…)`
- **Eigen tabbladen** (＋ Tab, alleen admin): Tekst, Lijst of Afvinklijst, bijv. inpaklijst, menu of huisregels; bij Lijst en Afvinklijst kan elke regel een link hebben
- **Zichtbaarheid per uitje**: de admin kan elk tabblad aan- of uitzetten (👁️ Zichtbaarheid). Een uitgezet tabblad is weg voor planners en lezers; alleen de admin ziet het nog (🚫)

## Starten

```bash
docker compose up -d --build
```

Open daarna `http://<ip-van-je-server>/` en log in met de admin-pincode **1234** (of wat je bij `ADMIN_PIN` hebt ingevuld).
Wijzig deze pincode direct via **⚙️ Instellingen**.

Alle gegevens staan in `./data` (SQLite-database, sessiesleutel en `uploads/` met bijlagen). Maak daar af en toe een back-up van.

## Rollen

| Rol      | Mag                                                                 |
|----------|---------------------------------------------------------------------|
| admin    | Alles: uitjes aanmaken/verwijderen, eigen tabbladen en zichtbaarheid, pincodes en beveiliging |
| planner  | Inhoud van uitjes bewerken: planning, locatie, gegevens, aanwezigen, bijlagen, eigen tabbladen |
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
| `MAX_UPLOAD_MB`| `25`      | Maximale grootte van bijlagen per upload |
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

> Gebruik je een reverse proxy (bijv. Nginx Proxy Manager)? Verhoog daar de maximale uploadgrootte,
> bijv. `client_max_body_size 25m;` in Nginx, anders lukken grotere bijlagen niet.

> Tip: zet de app niet rechtstreeks open op internet zonder HTTPS. Gebruik bijvoorbeeld een reverse proxy met een certificaat of een VPN (Tailscale/WireGuard).
