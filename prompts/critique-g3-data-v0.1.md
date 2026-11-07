# Critique gate G3 — data availability — v0.1

You know the public astronomical archives listed in `config/archives.yaml` (provided below) and their access paths. For the card below, decide whether an accessible archive holds the required observable at the required wavelength, resolution, cadence, depth and sample size.

Card: {card_yaml}
Archive map: {archives_yaml}

Return YAML:
- `verdict`: available | partial | needs_observations | proprietary
- `archives`: list of `{name, access, what_it_provides, gap}` — name the exact table, product or bucket where you can
- `volume_estimate`: rows or GB the analysis would touch, and whether it can run archive-side (ADQL/TAP) or needs downloads
- `access_plan`: 3-6 steps a Python script would take (astroquery, pyvo, lightkurve, boto3)
- `licence_notes`: anything that restricts use (data rights, proprietary periods)
- `reason`: 2 sentences

If the data do not exist yet but a scheduled release will provide them, say which release and date (e.g. Gaia DR4, 2026-12-02) and return `partial`.
