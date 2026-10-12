# Changelog

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
