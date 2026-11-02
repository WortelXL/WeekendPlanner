# Changelog

## [0.0.9] - 2026-11-02

### Toegevoegd
- **Linknaam per regel** in Lijst en Afvinklijst: geef de link een eigen naam (hyperlink), bijv.
  🔗 *Tickets bestellen* in plaats van 🔗 *teso.nl*. Leeg gelaten? Dan wordt de websitenaam getoond.
  Het volledige webadres zie je als je met de muis over de link gaat.

### Migratie
- Bestaande databases worden automatisch bijgewerkt; bestaande links tonen de websitenaam.

## [0.0.8] - 2026-11-02

### Toegevoegd
- **Link per regel in Lijst en Afvinklijst**: bij elke regel kun je een webadres invullen (snel-toevoegen of ✏️ bewerken).
  De link verschijnt als klikbaar label met de websitenaam (bijv. 🔗 teso.nl) en opent in een nieuw tabblad.
  `www.voorbeeld.nl` wordt automatisch `https://www.voorbeeld.nl`; alleen http(s) is toegestaan.

### Migratie
- Bestaande databases worden automatisch bijgewerkt.

## [0.0.7] - 2026-11-02

### Toegevoegd
- **Links in het tabblad Bijlagen** (knop **🔗 Link toevoegen**, planner/admin): webadres met een eigen naam en
  optionele omschrijving, bijv. "Website vakantiepark" of "Boottijden". `www.voorbeeld.nl` wordt automatisch
  `https://www.voorbeeld.nl`. Links openen in een nieuw tabblad.
- **Webadressen in tekst worden vanzelf klikbaar**: in omschrijvingen, notities, bijzonderheden, praktische info,
  gegevens, eigen tabbladen en bij bijlagen.
  - Eigen linktekst (hyperlink) met `[Boekingssite](https://www.voorbeeld.nl)`.

### Beveiliging
- Alleen `http`- en `https`-links zijn toegestaan (geen `javascript:` e.d.); ook de server controleert dit.
- Links vallen onder de zichtbaarheid van het tabblad Bijlagen.

## [0.0.6] - 2026-11-02

### Gewijzigd
- **Uitgezette tabbladen zijn nu weg voor planners én lezers.** Alleen de admin ziet een uitgezet tabblad nog
  (gemarkeerd met 🚫), zodat hij het kan voorbereiden en later aanzetten via 👁️ Zichtbaarheid.
- De server stuurt de gegevens van uitgezette tabbladen niet meer naar planners en weigert wijzigingen
  door planners in die tabbladen (bijv. aanwezigen, contactpersonen, bijlagen of regels van een eigen tabblad).

## [0.0.5] - 2026-11-02

### Gewijzigd
- **Eigen tabbladen beheren is alleen voor de admin**: de knop **＋ Tab** en het hernoemen, van soort wisselen,
  verplaatsen en verwijderen van eigen tabbladen zijn alleen zichtbaar en toegestaan voor de admin.
  Planners kunnen de inhoud (tekst en regels) wel blijven bewerken en afvinken.
- **👁️ Zichtbaarheid is alleen voor de admin**: alleen de admin kan tabbladen voor lezers aan- of uitzetten.
  Planners zien verborgen tabbladen nog wel (gemarkeerd met 🚫).
- Ook de server weigert deze acties voor planners (niet alleen verborgen in de pagina).

## [0.0.4] - 2026-11-02

### Toegevoegd
- **Eigen tabbladen** per uitje (knop **＋ Tab**, planner/admin), met naam, pictogram en soort:
  - 📝 **Tekst**: vrij tekstveld (bijv. huisregels).
  - 📋 **Lijst**: regels met omschrijving en bijzonderheden (bijv. menu).
  - ✅ **Afvinklijst**: regels om af te vinken met voortgangsbalk (bijv. inpaklijst, boodschappen).
  - Tabbladen hernoemen, van soort wisselen, naar links/rechts verplaatsen en verwijderen.
- **Tabblad Bijlagen**: bestanden uploaden (klikken of slepen, meerdere tegelijk) met omschrijving.
  - Foto's als voorvertoning; foto's en PDF's openen in de browser, andere bestanden worden gedownload.
  - Maximale uploadgrootte instelbaar met `MAX_UPLOAD_MB` (standaard 25 MB).
  - Bestanden staan in `data/uploads/` en worden verwijderd als het uitje wordt verwijderd.
- Eigen tabbladen en Bijlagen doen mee in **👁️ Zichtbaarheid**.

### Beveiliging
- Bestandstype wordt bepaald door de server (niet door de browser); onveilige types worden altijd als download
  aangeboden en bijlagen krijgen een strikte Content-Security-Policy.
- Lezers kunnen bijlagen van een verborgen tabblad ook niet via een directe link openen.

### Migratie
- Bestaande databases worden automatisch bijgewerkt.

## [0.0.3] - 2026-10-22

### Toegevoegd
- **Tabblad Aanwezig** per uitje: wie er komen, met per persoon een veld voor bijzonderheden
  (dieet, allergie, aankomsttijd, …).
  - Snel toevoegen via naam + bijzonderheden, of meerdere tegelijk (één per regel, `Naam: bijzonderheden`).
  - Aantal aanwezigen zichtbaar op het uitje-kaartje in het overzicht.
- **Zichtbaarheid per tabblad** (knop 👁️ Zichtbaarheid, planner/admin): Planning, Dagplanning, Locatie,
  Gegevens en Aanwezig per uitje aan/uit zetten voor lezers.
  - Verborgen tabbladen blijven voor planners en admin zichtbaar, gemarkeerd met 🚫.
  - Gegevens van verborgen tabbladen worden ook door de server niet naar lezers gestuurd.

### Opgelost
- Versienummer in de app en op `/health` (onderdeel van 0.0.2, maar `app.py` en `README.md` waren niet meegekomen).
- Op mobiel schuift het actieve tabblad automatisch in beeld.

### Migratie
- Bestaande databases worden automatisch bijgewerkt; alle tabbladen staan standaard aan.

## [0.0.2] - 2026-10-12

### Toegevoegd
- **Status per uitje**: Concept, Gepland of Gaande.
  - Status kiezen bij aanmaken en wijzigen via de keuzelijst naast de titel (planner/admin).
  - Filter op status in het overzicht; gaande uitjes staan bovenaan met een oranje rand.
  - Een gaand uitje opent direct op de dagplanning van vandaag.
- **Tabblad Dagplanning** met een sub-tabblad per dag (Dag 1, Dag 2, …):
  - Thema en notities per dag.
  - Tijdlijn van de onderdelen; wat nu bezig is krijgt het label "nu".
  - Knop om direct een onderdeel voor die dag toe te voegen.
- Versienummer zichtbaar in de app.

### Gewijzigd
- In het tabblad Planning linkt elke dag naar de bijbehorende dagplanning.

### Migratie
- Bestaande databases worden automatisch bijgewerkt; bestaande uitjes krijgen de status "Gepland".

## [0.0.1] - 2026-10-12

### Toegevoegd
- Eerste versie: Flask + SQLite in Docker op poort 80.
- Pincode-login met rollen admin, planner en lezer.
- Vergrendeling na 5 foute pogingen voor 10 minuten (instelbaar door admin).
- Uitjes met planning, locatie (kaart en route) en gegevens (contactpersonen, overige info).
- Admin-instellingen: pincodes per rol, beveiliging, vergrendelingen vrijgeven, sitetitel.
