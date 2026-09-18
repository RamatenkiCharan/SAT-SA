# SUPERVISORY RANKING DIAGNOSTIC

## 1. Executive finding

**OBSERVED:** the robust protocol's published Top-K is raw finding recall, not ReviewBudgetOptimizer output. The optimizer therefore cannot explain that published metric. The held-out unit is a detector-type target within a CSE scenario; Top-5 asks how many of all such targets across 72 scenarios appear in five global findings. This is a granularity/objective mismatch for a small supervisory queue, not evidence that a single correct answer was missed.

## 2. Exact current metric and evaluation unit

**OBSERVED:** `GroundTruthScenario` is one generated CSE-period scenario. Its label is a *set* of detector types. A finding is one detected `(cse_id, finding_type)` pair. `recall@K = unique true detector-type pairs in the first K priority-sorted findings / all true detector-type pairs across held-out scenarios`. It is not scenario recall, entity recall, nor optimizer selection recall.

Held-out scenarios: 72; ground-truth detector targets: 39; findings: 66.

## 3. Raw finding ranking versus optimizer selection

**OBSERVED:** raw Top-1/3/5 = 0.0256/0.0769/0.1282. Recomputed raw = 0.0256/0.0769/0.1282. Optimizer (budget 5, default 10% control) = 0.0256/0.0769/0.1282.

## 4. Deduplication and multiple positives

**OBSERVED:** candidates before/after deduplication: 66/37. Removed findings: 29 (true targets: 29, non-targets: 0).
**OBSERVED:** scenarios with 0/1/2+ targets: 45/15/12. Multiple targets make a global five-item recall denominator intentionally demanding.

## 5. Score and component distributions

**OBSERVED:** true-target score: n=65, mean=0.7096, median=0.6700, sd=0.0553, min=0.6668, p25=0.6700, p75=0.7500, max=0.8500. Non-target score: n=1, mean=0.6625, median=0.6625, sd=0.0000, min=0.6625, p25=0.6625, p75=0.6625, max=0.6625. Pairwise P(score_positive > score_negative), ties half: 1.0000.

- **T** positive: n=65, mean=0.7385, median=0.6667, sd=0.1381, min=0.6667, p25=0.6667, p75=0.6667, max=1.0000; negative: n=1, mean=0.6667, median=0.6667, sd=0.0000, min=0.6667, p25=0.6667, p75=0.6667, max=0.6667
- **D** positive: n=65, mean=0.6853, median=0.6667, sd=0.1225, min=0.6000, p25=0.6000, p75=0.7333, max=1.0000; negative: n=1, mean=1.0000, median=1.0000, sd=0.0000, min=1.0000, p25=1.0000, p75=1.0000, max=1.0000
- **B** positive: n=65, mean=0.8338, median=0.8500, sd=0.0619, min=0.5000, p25=0.8000, p75=0.8500, max=0.9000; negative: n=1, mean=0.5000, median=0.5000, sd=0.0000, min=0.5000, p25=0.5000, p75=0.5000, max=0.5000
- **C** positive: n=65, mean=1.0000, median=1.0000, sd=0.0000, min=1.0000, p25=1.0000, p75=1.0000, max=1.0000; negative: n=1, mean=0.7500, median=0.7500, sd=0.0000, min=0.7500, p25=0.7500, p75=0.7500, max=0.7500
- **A** positive: n=65, mean=0.0000, median=0.0000, sd=0.0000, min=0.0000, p25=0.0000, p75=0.0000, max=0.0000; negative: n=1, mean=0.0000, median=0.0000, sd=0.0000, min=0.0000, p25=0.0000, p75=0.0000, max=0.0000

## 6. Detector, CSE, period, uncertainty, and criticality diagnostics

- **COVERAGE_GAP:** findings=13, targets=13, mean_priority=0.6967, raw_top5=0, dedup_removed=7
- **ESCALATION_GAP:** findings=11, targets=11, mean_priority=0.7933, raw_top5=2, dedup_removed=0
- **FAST_CLOSURE:** findings=10, targets=9, mean_priority=0.7565, raw_top5=3, dedup_removed=0
- **REPEATED_UNRESOLVED_ALERTS:** findings=32, targets=32, mean_priority=0.6700, raw_top5=0, dedup_removed=22

**OBSERVED:** CSEs=25; periods=25; selected controls=1. Mean uncertainty A: targets=0.0000, non-targets=0.0000.
**OBSERVED:** criticality-only diagnostic subtracts `w_C*C` from the stored fused score without changing production code. It changes ordering only where C differs; full recalculation is unnecessary because it is an additive component.
- Raw Top-5 target recall with C diagnostic removal: 0.1282; original: 0.1282.

## 7. Optimizer structural effects

- rank 1: `e4287c90` type=FAST_CLOSURE, target=True, priority=0.8500, marginal=1.0475, components priority/uncertainty/contradiction/coverage/diversity=0.8500/0.0000/0.0000/0.6000/0.1500, control=False.
- rank 2: `3a20ae09` type=ESCALATION_GAP, target=True, priority=0.7933, marginal=1.0277, components priority/uncertainty/contradiction/coverage/diversity=0.7933/0.0000/0.0000/0.6000/0.1500, control=False.
- rank 3: `2ca04e29` type=COVERAGE_GAP, target=True, priority=0.6967, marginal=0.9938, components priority/uncertainty/contradiction/coverage/diversity=0.6967/0.0000/0.0000/0.6000/0.1500, control=False.
- rank 4: `9d32a08d` type=REPEATED_UNRESOLVED_ALERTS, target=True, priority=0.6700, marginal=0.9845, components priority/uncertainty/contradiction/coverage/diversity=0.6700/0.0000/0.0000/0.6000/0.1500, control=False.
- rank 5: `e4885dd1` type=REPEATED_UNRESOLVED_ALERTS, target=True, priority=0.6700, marginal=0.0000, components priority/uncertainty/contradiction/coverage/diversity=0.6700/0.0000/0.0000/0.0000/0.0000, control=True.

## 8. Raw ranking table

|Raw rank|Scenario/CSE|Ground truth|Finding|Type|T|D|B|C|A|Score|Tier|Confidence|Dedup survivor|Optimizer rank|
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---:|
|1|a3cb725c|True|e4287c90|FAST_CLOSURE|1.000|1.000|0.750|1.000|0.000|0.8500|HIGH|0.960|True|1|
|2|4fab6795|True|c8567e86|FAST_CLOSURE|1.000|1.000|0.750|1.000|0.000|0.8500|HIGH|0.980|True|-|
|3|d26d1dbd|True|78581c3d|FAST_CLOSURE|1.000|1.000|0.750|1.000|0.000|0.8500|HIGH|0.980|True|-|
|4|8f52e93b|True|3a20ae09|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|2|
|5|8a2bb311|True|6e87f4c3|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|6|d2f70f2f|True|36faf4a4|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|7|abb3b0be|True|2f920ccb|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|8|a3cb725c|True|6ae1c377|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|9|3fffdff7|True|33deab36|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|10|4fab6795|True|36a8dc17|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|11|00f997e6|True|70127667|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|12|d21b1bee|True|21492a39|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|13|d26d1dbd|True|0734e988|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|14|4fb7152e|True|a207d289|ESCALATION_GAP|1.000|0.733|0.800|1.000|0.000|0.7933|HIGH|0.950|True|-|
|15|deadb419|True|70d3a2e3|FAST_CLOSURE|0.667|1.000|0.750|1.000|0.000|0.7500|HIGH|0.960|True|-|
|16|262247bd|True|b876ba1c|FAST_CLOSURE|0.667|1.000|0.750|1.000|0.000|0.7500|HIGH|0.930|True|-|
|17|7df79536|True|602c5837|FAST_CLOSURE|0.667|1.000|0.750|1.000|0.000|0.7500|HIGH|0.980|True|-|
|18|e714c930|True|48bccea9|FAST_CLOSURE|0.667|0.888|0.750|1.000|0.000|0.7219|MEDIUM|0.850|True|-|
|19|870d83da|True|d47ceee5|FAST_CLOSURE|0.667|0.856|0.750|1.000|0.000|0.7139|MEDIUM|0.840|True|-|
|20|3490d5f0|True|2ca04e29|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|True|3|
|21|3490d5f0|True|2e3c1dba|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|22|deadb419|True|1471baa2|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|True|-|
|23|deadb419|True|cb3ca48a|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|24|e714c930|True|d321fdb1|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|True|-|
|25|e714c930|True|baa7e5fa|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|26|356d0b87|True|4d469d30|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|True|-|
|27|356d0b87|True|b7181776|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|28|00f997e6|True|60e583ce|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|True|-|
|29|00f997e6|True|b153d78a|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|30|00f997e6|True|cc8d13b2|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|31|619fa278|True|d73ad5c1|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|True|-|
|32|619fa278|True|319d514b|COVERAGE_GAP|0.667|0.667|0.900|1.000|0.000|0.6967|MEDIUM|0.920|False|-|
|33|8f52e93b|True|e0de05ba|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|34|8f52e93b|True|b6178b33|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|35|8f52e93b|True|17540bb4|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|36|8f52e93b|True|d2ac1fcf|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|37|8f52e93b|True|c9b2c369|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|38|0c1775cb|True|9d32a08d|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|4|
|39|0c1775cb|True|c79c6323|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|40|d2f70f2f|True|88c1fee6|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|41|d2f70f2f|True|6952aa9a|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|42|abb3b0be|True|e4885dd1|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|5|
|43|abb3b0be|True|4e77663a|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|44|abb3b0be|True|fc41e426|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|45|3fffdff7|True|b5ea2096|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|46|3fffdff7|True|c6535c10|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|47|7df79536|True|b547a12e|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|48|7df79536|True|fd88adb1|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|49|7df79536|True|364e3042|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|50|7df79536|True|7826eaf3|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|51|7df79536|True|7cb9bab7|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|52|b4d28ee2|True|02e64b69|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|53|b4d28ee2|True|268fe0fc|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|54|b4d28ee2|True|37307668|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|55|b4d28ee2|True|44583a5b|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|56|b4d28ee2|True|c54d60aa|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|57|870d83da|True|61f06996|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|58|870d83da|True|3b129ff3|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|59|513d433d|True|7e4e191e|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|60|513d433d|True|01563bc6|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|61|513d433d|True|da7b376c|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|62|513d433d|True|dea812a9|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|63|513d433d|True|5afb72e5|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|False|-|
|64|c217d7d4|True|cdbfa67b|REPEATED_UNRESOLVED_ALERTS|0.667|0.600|0.850|1.000|0.000|0.6700|MEDIUM|0.900|True|-|
|65|d7951f41|True|9452d033|FAST_CLOSURE|0.667|0.867|0.500|1.000|0.000|0.6668|MEDIUM|0.840|True|-|
|66|2ec6a51f|False|279554e7|FAST_CLOSURE|0.667|1.000|0.500|0.750|0.000|0.6625|MEDIUM|0.910|True|-|

## 9. Fusion recomputation

**OBSERVED:** each stored score is the weighted sum `0.30T + 0.25D + 0.20B + 0.15C - 0.10A`, clamped to [0,1]. The raw table exposes the exact components and weights for independent checking. This diagnostic did not alter fusion.

## 10. Root-cause classification and decision

**SUPPORTED:** A — evaluation-definition problem; C — granularity mismatch; G — synthetic-population artifact. The metric measures detector-type-pair coverage across a many-positive population, while a small review budget necessarily covers only a small fraction.

**NOT SUPPORTED:** D/E/F/H as the primary explanation. The published metric does not use the optimizer, and deduplication is measured above. Fusion implementation is reproducible from stored components but its supervisory usefulness cannot be inferred from detector recall alone.

1. Is fusion correctly implemented? **OBSERVED: yes, subject to row-level recomputation shown above.**
2. Is raw ranking useful? **OBSERVED: not as measured by global pair recall@5; it is not enough to decide practical usefulness.**
3. Does optimizer substantially degrade published ranking? **OBSERVED: no evidence; it was not in the published metric.**
4. Is current Top-K aligned? **INFERRED: only partially; it ignores coverage/yield and multiple valid targets.**
5. Is the benchmark appropriate for detector evaluation? **OBSERVED: yes for the reported synthetic detector protocol; UNVERIFIED for supervisory queue utility.**
6–8. Change fusion, optimizer, or methodology? **Do not change fusion/optimizer. Evaluate a newly held-out supervisory-utility protocol before any change.**
9. Remain unchanged: held-out labels, generator, fusion, detector, optimizer, and schema.
