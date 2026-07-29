# AGCF — Agentic Governance & Control Framework

**v0.9.3 (draft for review) · 28 July 2026**

A vendor-neutral reference architecture and self-assessment instrument for
governing AI agents, assistants and automation. 106 controls across 12 domains,
each tagged with the organization size and autonomy level at which it becomes
mandatory, and each mapped to the standards an auditor or enterprise customer is
likely to ask about.

Designed to be used in an afternoon rather than adopted over a year.

---

## Start here

| If you want to… | Open |
|---|---|
| Assess where you stand | **[`AGCF-assessment.html`](AGCF-assessment.html)** — open it in a browser. No install, no server, no data leaves the page. |
| Read the control catalogue | **[`AGCF-framework.md`](AGCF-framework.md)** — the 106 controls, their evidence requirements, and the standards crosswalk. |
| Build the thing | **[`AGCF-implementation.md`](AGCF-implementation.md)** — collapses the catalogue into nine buildable components, with a prompt library for executing each in your own environment. |
| Avoid the failure modes | **[`AGCF-implementation-field-notes.md`](AGCF-implementation-field-notes.md)** — twelve lessons from implementing these controls on a live stack. Read before you deploy, not after. |
| Consume it programmatically | **[`catalog.json`](catalog.json)** — the full catalogue, machine-readable. |

## What it is, and what it is not

**It is** a reference architecture plus a control catalogue. It says where a
control physically sits at runtime — what evaluates a request before the model
reasons, what stands between a decision and an action, what writes the record,
and what feeds back.

**It is not** a management system standard (ISO/IEC 42001 is that, and it is
certifiable; this is not). **It is not** a risk taxonomy (OWASP's LLM and
Agentic Top 10s and MITRE ATLAS are those, and they are better at it than a
general framework can be). **It is not** a substitute for legal advice on any
regime it cites.

The published material clusters into management systems, which tell you what
organizational functions must exist, and risk taxonomies, which tell you what
goes wrong. Neither tells you that the policy gate has to sit between the
planner and the tool call rather than in the system prompt. The gap between them
is an *architecture*. This occupies that gap and stays deliberately thin, so it
sits beside the others rather than competing with them.

## The 12 domains

| | Domain | Controls |
|---|---|---|
| GOV | Governance & Accountability | 9 |
| INV | AI Register, Classification & Risk Tiering | 8 |
| DAT | Data Boundary, Provenance & Sovereignty | 10 |
| IDA | Identity, Authority & Attribution | 9 |
| ING | Ingress Trust & Content Integrity | 8 |
| POL | Policy Enforcement & Guardrails | 8 |
| ACT | Action Control & Blast Radius | 10 |
| HUM | Human Oversight & Competence | 11 |
| OBS | Observability & Evidence | 9 |
| ASR | Assurance, Evaluation & Red Teaming | 9 |
| IRR | Incident Response, Recovery & Retirement | 8 |
| LRN | Learning & Continuous Improvement | 7 |

## Design commitments

1. **Autonomy, not organization size, is the primary risk axis.** A one-person
   shop running an agent with write access to production is taking on more risk
   than a thousand-person company running a read-only FAQ bot.
2. **Containment carries the weight, not approval.** Published containment
   research reports approval rates around 93% on permission prompts — a gate
   asked too often is a click-through, not a decision. Every control that leans
   on a human is paired with one that holds when the human clicks Approve.
3. **Every control names its evidence.** A control you cannot evidence is a
   control you do not have.
4. **The gap between "implement" and "develop" is preserved.** Some absent
   controls are procurement. Others have no off-the-shelf answer and require
   design. Conflating them is how programmes miss dates.
5. **Nothing is claimed to be settled that isn't.** Where the underlying
   standard is draft or moving, the framework says so.

## Standards crosswalk

Every control maps to **NIST AI RMF 1.0**, **ISO/IEC 42001:2023 Annex A**, the
**EU AI Act**, and where applicable **OWASP Top 10 for LLM Applications (2025)**,
**OWASP Top 10 for Agentic Applications (v1.0)**, the **ASI threat classes**, and
**MITRE ATLAS**. The crosswalk table is in `AGCF-framework.md` §10.

NIST's SP 800-53 Control Overlays for Securing AI Systems (COSAiS) has planned
single-agent and multi-agent overlays; as of July 2026 those remain at
concept-paper and annotated-outline stage. Where AGCF's positions may need to
move once those publish, `AGCF-framework.md` §9 says so explicitly.

## Status

**Pre-1.0 and marked draft for review.** Control IDs are stable enough to cite,
but wording and tier assignments may still change. v0.9.3 rewrote all 106 control
statements in Simplified Technical English (active voice, named doer, second
person, one term per concept) and passes the project's own two-stage STE gate at
zero findings.

The versioned artifacts move together: the tag on this repository always equals
the version string in `AGCF-framework.md`.

**Not included here:** the Implementation Guide refers to a separate worked
example applying the whole guide to one real self-hosted stack. That file is not
published in this repository.

## Related work

The **[Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)**
and its Agent Control Specification address the runtime enforcement layer —
deterministic, stateless policy evaluation at defined intervention points. AGCF
is complementary rather than competing: it covers the organizational and
architectural layer around that enforcement, including the authorization and
accountability records that a policy manifest presupposes but does not itself
provide. Where the two overlap, they largely agree, which is some evidence the
shape is right.

## Contributing

Issues and discussion are welcome, particularly:

- controls that are wrong, missing, or mis-tiered
- evidence requirements that cannot actually be produced in practice
- crosswalk errors against any of the cited standards
- field reports — implementations that failed in ways the field notes don't cover

## License

See [`LICENSE`](LICENSE).
