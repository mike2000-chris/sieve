# Converge — scoring — v0.1

Score the gated card on five dimensions, each 0-3, using the gate outputs. Do not re-litigate the gates; translate them.

Card: {card_yaml}
Gate logs: {gate_logs_yaml}
Budget: {budget_yaml}

- `novelty`: 3 = G2 open with high confidence; 2 = open with low confidence or partly_done with a clear gap; 1 = partly_done, small gap; 0 = done.
- `feasibility`: 3 = archive-side query, < 10 human hours, no downloads; 2 = modest downloads or < 25 hours; 1 = heavy compute or > 25 hours; 0 = needs observations or proprietary data.
- `information_value`: how much a null result constrains, independent of detection (3 = first limit of its kind or a limit on a population; 0 = null result says nothing).
- `confounder_robustness`: copy G4 `robustness`.
- `cost_inverted`: 3 = under 5% of monthly caps; 0 = exceeds a cap.

Return YAML: the five scores, `total`, `quick` (true if feasibility = 3 and estimated human hours < 10), `ambitious` (true if feasibility <= 1 or total human hours > 25), `dominant_confounder` (copy from G4), `one_line_rationale`.
