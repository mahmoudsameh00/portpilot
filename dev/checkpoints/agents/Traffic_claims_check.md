# Shared traffic claims — Final Checkpoint

Stabilization R5/R6, implemented 2026-11-11. M17 SQL and its acceptance thresholds are unchanged.

The shared policy is `pipelines/agents/traffic_claims.py`. The deck's V10 entry point and human analysis edits
delegate to it; finance Q&A calls it and the supervisor inherits that check. Model-generated analysis notes are
checked before the Writer: unsafe notes end a fresh run as `output_invalid`; the existing failed-revise route
restores a previously reviewable pack. No extra model call or silent rewrite is introduced.

Only a cited, successful `finance_kpi` result from the live/test/scenario `kpi_traffic_link` view supports a claim.
Dynamic evidence IDs work; matching an ID or copying a verdict into a document result does not. Explicit weeks
must be covered, and ambiguous mixed results are refused. Association needs `link`; a negative measured statement
needs `no_link`; insufficient-history wording needs the null verdict. Invoice-count evidence cannot establish
monetary or news effects, nor causation in either direction. Explicit epistemic disclaimers remain valid.

The policy normalizes Arabic spelling/diacritics/digits, checks contrast and short referential clauses, and uses
the question/slots to identify implicit financial subjects. Unfamiliar joint claims are conservatively refused
with fixed EN/AR wording as a repair hint. Those same six fixed statements are supplied by the finance tool.
This is a bounded deterministic language guard, not exhaustive semantic understanding. Real-model evaluation
must still measure false refusals and paraphrase coverage before traffic acceptance closes.

Validation: 66 fixed adversarial cases, each through the policy, deck entry point, finance Q&A, supervisor Q&A
and note checker; six code-written statements; provenance/citation/ambiguity tests; short-answer and slot tests;
the real Insight-node stop/restore path with a fake structured model. All four phases pass, with zero data or
migration artifact changes. The fixture is SHA-256 pinned in the script. Included in database-free CI.

No database or provider calls. The original frozen golden sets and recorded evaluations remain untouched.
Full database-backed deck/agent checks and repeated real-model acceptance remain owner workflow gates.

## 2026-11-12 — after the first real-model measurement (traffic plan Phase 6, run `tl1`; D-TL-11)

Problem found by the real models: in the packs acceptance run, 7 of 11 golden weeks stopped `output_invalid` at
`insight_notes V10`. The cached notes showed mostly true denials that the patterns did not know ("no statistical
link", "did not show a measured link", "is not claimed to move with", "not measurable yet"), a threshold week read
as the claim's week ("null before week 13"), a contrast clause given both domains although it stated only a
traffic fact, and every caveat failing "cite one result" because caveats carry no evidence ids. One refused
sentence stopped the whole week's pack.

Fixes: the patterns accept those denial forms (a fixed qualifier list, so "no doubt the link …" is still not a
denial); threshold weeks are ignored when selecting the cited row; only a relation-stating clause of a contrast
inherits both domains; caveats are judged against the run's own M17 results by provenance (`traffic_ids`). The
Insight node now repairs before it stops: `repair_notes` removes the refused sentence, adds the fixed wording of
the run's measured verdict and the M17 id, and records one line per repair in `normalized`. Without a single
measured verdict nothing is repaired and the stop / restore path is the one validated before.

Validation: Phase 4 now proves both branches (unrepairable → stop / restore; repairable → fixed wording, Writer
runs; clean notes untouched). New Phase 5: `fixtures/traffic_claims_real.json`, 53 sentences written by the real
models, labels reviewed by hand (50 sound pass, 3 unsafe refused), SHA-256 pinned; the repair on a mixed EN note
set and an Arabic causal sentence; all 119 pinned cases (66 + 53) end as notes with no problem. The original 66
cases and their hash are unchanged. Still a bounded guard: new paraphrases can be refused, at the cost of one
replaced sentence.
