---
name: soc-supervisory-analytics
description: Domain knowledge for SAT-SA (Supervisory Analytics Tool for SOC Assessment, SIH problem 26157) — the distinction between a SOC and a supervisory analytics layer, the Evidence-to-Assurance framing, execution gaps, negative space, and how SAT-SA is positioned against existing tools (SOC-CMM, SIEM, SOAR, EDR/XDR, maturity questionnaires). Use this whenever discussing what SAT-SA is/isn't, explaining the problem to a new team member or judge, writing a pitch or one-minute explanation, or answering "isn't this just a SOC dashboard / SOC-CMM / maturity questionnaire" style questions. Trigger even for casual questions like "explain SAT-SA" or "what's the difference between a SOC and this tool."
---

# SOC Supervisory Analytics Domain Knowledge

## The core distinction (get this right before anything else)

```
SOC        = doctor treating the patient        -> fights cyber threats
SAT-SA     = examiner assessing whether the     -> evaluates whether the fight
             hospital's treatment system works     is actually effective
```

SAT-SA is **not** a SOC, SIEM, SOAR, EDR/XDR, real-time monitoring platform, or centralized telemetry collector. It does not operate defenses. It analyzes the operational evidence a SOC already produces (alerts, investigations, cases, escalations, closures) to tell a supervisor where to spend limited manual review effort.

## The central problem: documentation vs. operational evidence

```
DOCUMENTATION            "We investigate critical alerts."
                          "We escalate serious incidents."
        vs.
OPERATIONAL EVIDENCE     "Many critical alerts closed in 4 minutes."
                          "Escalation records missing."
                          "Same asset repeatedly alerts, no remediation evidence."
```

A CSE (Critical Sector Entity) can pass every self-assessment and questionnaire while its actual evidence tells a different story. Manual review can catch this; SAT-SA's job is to scale that catching.

## Two core concepts — know these cold

**Execution gap**: a documented/expected process technically exists but operational evidence suggests it isn't being executed effectively (e.g., 98% of alerts "closed" per KPI, but median investigation time is trivial and escalation records are missing). Classic Goodhart's-law pattern — a metric optimized while the underlying outcome degrades.

**Negative space**: evidence that *should* exist under the expected operating context but doesn't. Low alert volume from a critical environment isn't automatically good news — it might mean genuinely low activity, or it might mean a monitoring blind spot. SAT-SA never concludes "insecure" from absence alone; it raises a **hypothesis** requiring context (peer behavior, historical baseline, data-quality check) before a human reviews it.

## Why this isn't "just SOC-CMM" or "just a dashboard"

| Approach | Answers | Uses operational evidence? | Finds execution gaps? | Finds negative space? |
|---|---|---|---|---|
| Self-assessment / questionnaire | What does the org report? | Mostly self-reported | Limited | Limited |
| SOC-CMM / maturity assessment | How mature is the capability? | Some | Not the exact focus | Not the exact focus |
| SIEM / SOAR / EDR / XDR | What security events occurred? | Yes | Not primary | No |
| Manual supervisory review | What does evidence reveal? | Yes | Yes | Yes |
| **SAT-SA** | Where does evidence warrant supervisory attention? | **Yes** | **Yes (core)** | **Yes (core)** |

Never claim "no existing solution exists" — that's an easy pitch to destroy. The correct positioning: *"Existing maturity frameworks and self-assessment tools measure capability and maturity. Operational SOC platforms manage security events. SAT-SA addresses the gap between them by analyzing submitted operational evidence for execution gaps and negative space, while preserving human supervisory judgment."*

## The one-sentence identity

> "Don't ask whether a SOC says it works. Analyze the evidence of how it actually operates."

## The "wow moment" pattern (use for demos/pitches)

A KPI dashboard shows CSE-B outperforming CSE-A (99% vs 97% SLA compliance). SAT-SA flags CSE-B for supervisory attention anyway, because: critical alerts closed unusually fast, low investigation evidence, missing escalation, repeated alerts, and significant peer deviation. The lesson to state out loud: *"The KPI looks healthy, but operational evidence tells a different story."*

## Guardrails when explaining or writing about this system
- Never say the system determines whether a CSE "is secure" — too broad.
- Never say it "detects negligence" — too strong an accusation for a supervisory-attention tool.
- Never say it "replaces NCIIPC auditors/examiners" — it recommends, humans decide.
- Always frame findings as hypotheses for review, not verdicts.
