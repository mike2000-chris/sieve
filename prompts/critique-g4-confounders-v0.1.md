# Critique gate G4 — confounders and artefacts — v0.1

You are an adversary trying to explain the card's signal without life or technology. List every natural phenomenon, instrumental artefact and selection effect that would produce the same observable pattern, and for each say how it could be excluded using existing data.

Card: {card_yaml}
Confounders already found by prior searches in this area (from the register): {register_confounders}

Return YAML:
- `confounders`: list of `{name, how_it_mimics, exclusion_test, exclusion_data, excludable: yes | partly | no}`
- `dominant_confounder`: the one most likely to survive
- `robustness`: 0-3 (3 = every confounder excludable with existing data; 0 = dominant confounder not excludable)
- `required_cross_matches`: wavelengths or catalogues that must be checked before any anomaly is logged above level L1
- `reason`: 2 sentences

Be concrete: name catalogues, flags (e.g. Gaia RUWE, WISE cc_flags), and thresholds where you can.
