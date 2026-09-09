---
name: soc-supervisory-analytics
project: SAT-SA (SOC Supervisory Analytics)
order: 02
---

# Skill 02 — SOC Supervisory Analytics (Domain Knowledge)

## Purpose
Ground every downstream design decision in how a real SOC actually operates.
Supervisory analytics is analytics *about* the SOC's detection and response
process — not the primary detections themselves. Conflating the two is the most
common architectural mistake in this space.

## Core distinction: primary vs. supervisory layer

| | Primary layer (SIEM/EDR/XDR/SOAR) | Supervisory layer (SAT-SA) |
|---|---|---|
| Question answered | "Is something malicious happening?" | "Is the detection/response process itself working?" |
| Input | Raw telemetry | Telemetry about the primary layer: alert volumes, source health, analyst actions, rule coverage, timing |
| Output | Alerts / incidents | Supervisory findings: coverage gaps, timeliness breaches, consistency anomalies, blind spots |
| Failure mode if broken | Missed attack | Missed *awareness that detection is broken* |

SAT-SA exists because a SOC can look "green" on its primary dashboards while
silently losing coverage (a log source stops flowing, a detection rule bit-rots
against a platform change, an analyst queue backs up) and nobody notices until
an incident post-mortem asks "why didn't we see this?"

## SOC operating model to design around

- **Tiering**: L1 triage (volume, first-pass classification) → L2 investigation
  → L3 threat hunting/engineering. Supervisory signals differ by tier: L1 cares
  about queue depth and time-to-first-touch; L3 cares about hunt coverage and
  rule freshness.
- **Shift structure**: 24/7 SOCs have handoff gaps — a common blind spot window
  is shift changeover. Model shift boundaries explicitly.
- **Escalation paths**: know who a supervisory finding routes to (SOC lead vs.
  detection engineering vs. platform/data engineering) — a coverage gap caused
  by a broken log forwarder is not the same fix as a stale detection rule.
- **Alert fatigue dynamics**: high false-positive rates on the *primary* layer
  cause analysts to habitually dismiss/snooze — this is itself a supervisory
  signal (see skill 04) distinct from raw alert volume.

## Key SOC KPIs the supervisory layer should be able to speak to

- MTTD (mean time to detect), MTTR (mean time to respond/remediate)
- Alert-to-analyst ratio, queue depth over time
- False positive rate trend per rule/source
- Detection coverage against a framework (typically MITRE ATT&CK technique
  coverage) — see skill 05 for how gaps in this map to negative space
- Analyst consistency (do different analysts triage similar alerts similarly?)
- Source/rule freshness (last validated, last fired, last tuned)

## What "supervisory" must NOT become
- A second SIEM. SAT-SA consumes metadata/telemetry-about-telemetry; it should
  not re-ingest and re-analyze raw security events for primary detection.
- A performance-management surveillance tool aimed at individual analysts
  without governance — this is a real organizational risk; findings about
  analyst behavior must be aggregated/anonymized per policy unless explicitly
  scoped otherwise in requirements (skill 01), and that scoping decision must
  be made by SOC leadership + HR/legal, not by the engineering team alone.

## Design implication for later skills
- Skill 03 (data modeling) must represent "coverage" as a first-class entity
  (source × technique × time), not just events.
- Skill 04 (signal engine) must be able to distinguish "no alerts because
  nothing happened" from "no alerts because monitoring is broken" — this is the
  central hard problem the whole project exists to solve.
- Skill 05 (negative-space detection) is the direct technical answer to that
  distinction.
