# Changelog

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
