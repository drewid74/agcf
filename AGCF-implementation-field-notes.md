# AGCF field notes — lessons from implementing the controls

Companion to `AGCF-implementation.md`. That document describes what to build.
This one records what went wrong while building it, and which of those failures
generalize.

Every note here came out of implementing AGCF controls on a real agent stack.
They are written stack-agnostically because the failure modes are not specific
to any proxy, database, or orchestrator — they are properties of the control
*shape*. Where a concrete technology appears it is illustrative.

The organising observation, which most of these are instances of:

> A control that is present, correct, and tested can still fail to protect
> anything — because it was never invoked, never durable, never distinguishable
> from breakage, or never fed. Correctness is the easy half.

---

## 1. A refusal must say whether a decision was made

**Observed.** A fail-closed control refused every request for ninety minutes.
The cause was a misconfiguration: the store it consults was unreachable, so it
refused, exactly as designed. From outside, this was indistinguishable from a
deliberate stack-wide stop — same status code, same shape of error. The two
differed only in a message body nobody was parsing.

**Why it generalizes.** Every fail-closed control has two refusal modes that
look identical and mean opposite things:

| | Decided? | Expected? | Should page? |
|---|---|---|---|
| Refused **by policy** | yes — someone stopped it | yes | no |
| Refused **by degradation** | no — the control plane is broken | no | **immediately** |

Collapsing them costs you the ability to tell a working safety system from a
broken one. Worse, it means anyone who can perturb the control's dependencies —
a DNS blip, an env change, a typo — can cause a total denial of service *that
looks like a legitimate safety action*. **Availability failures should not be
able to disguise themselves as security decisions.**

**Do.** Make the distinction machine-readable at the boundary, not just in a
log line. A response header (`X-Refusal: policy | degraded`), a stable `reason`
field, and separate metric labels. Alert on the degraded counter at *any*
non-zero rate — there is no acceptable level of "the control plane is down and
nobody decided that."

**Maps to.** ACT-07, OBS-05, OBS-07.

---

## 2. Fail loud at startup; fail closed at runtime

**Observed.** The misconfigured process started successfully, reported healthy,
and then refused everything it was asked to do.

**Why it generalizes.** Failing closed is the right response to a dependency
dying *while running* — that is a real outage and refusing is safe. It is the
wrong response to a **misconfiguration**, because it produces a process that is
simultaneously "up" and "useless", and that state is hard to see and easy to
misattribute.

The two deserve different treatment:

- **Startup:** validate the dependency. If it is missing, unreachable, or the
  schema is wrong — **refuse to start.** A crash-loop is loud, obvious in any
  process listing, and impossible to mistake for a policy decision.
- **Runtime:** if the dependency dies later, fail closed and alert per §1.

**Do.** Give every control a preflight that checks the whole chain it depends
on — config present, driver importable, dependency reachable, schema correct,
read path working — and run it at import or as an init step. Report what it
found; a control that is *already* enforcing at startup (a stop left on from
yesterday) should say so, so it is not mistaken for today's breakage.

**Maps to.** ACT-07, OBS-01.

---

## 3. Health must mean "can do its job", not "is running"

**Observed.** A liveness probe returned success for the entire ninety-minute
outage, because the process *was* alive. It was simply refusing everything.

**Why it generalizes.** Liveness and correctness are different questions, and
for a control the second is the only interesting one. A security component that
answers "am I running?" is measuring the wrong thing: the failure mode you care
about is precisely the one where it runs and does not work.

**Do.** Point the healthcheck at the preflight from §2, not at a socket. Health
should fail when the control cannot enforce.

**Maps to.** OBS-01, ACT-07.

---

## 4. A control installed by runtime mutation is not deployed

**Observed.** Control code reached a container by copying files into the
running instance; its dependency was installed by executing a package manager
inside that instance. Both worked. Both vanished the moment the container was
correctly recreated, turning a routine config fix into a crash-loop.

**Why it generalizes.** Anything mutated into a running instance is invisible
to the declarative config and does not survive replacement. The deployment
descriptor and the running reality can disagree completely, and the descriptor
is the one people read during an incident.

**Do.** Dependencies belong in the image. Control source belongs in a mount or
the image. Nothing belongs in a live-container mutation. A useful smell test:
**if you would have to repeat a command after a restart, the control is not
deployed — it is being performed.**

Verify from the process, never from the file: read the environment the running
process actually has, not the one the config declares. On most orchestrators a
"restart" reuses the existing environment while a "recreate" reloads it, and
that distinction is exactly where a correct-looking config hides a stale one.

**Maps to.** ACT-03, ASR-06, OBS-01.

---

## 5. A fail-closed handler catches one exception type; everything else walks past it

**Observed.** A cache read in a hot-path control had a race: check a value is
non-null, then separately return it. A concurrent invalidation between those
two statements returned null, and the caller — which iterated the result —
raised a `TypeError`.

Every fail-closed call site caught the control's *own* error type. `TypeError`
is not that type. The refusal path was bypassed entirely, and what happened
next depended on whatever generic handler caught it.

**Why it generalizes.** "Fail closed" is usually implemented as
`except ControlError: refuse`. That is a promise about **one** failure mode.
Any *other* exception — a bug, a type error, a library change, an unexpected
`None` — escapes to the caller's default behaviour, and default behaviour is
usually not "refuse".

**Do.** Two things:

1. Make refusal the **default path**, not a specific `except` clause. Catch
   broadly at the enforcement boundary and treat *any* unexpected failure as a
   refusal, then narrow the reason for reporting. An unclassified failure in a
   security control is a refusal by definition.
2. Test the control under concurrency before you introduce concurrency. This
   race was harmless while a single-threaded caller was the only consumer, and
   became live the moment the control was wrapped for a threadpool. The bug did
   not change; the caller did.

**Maps to.** ACT-07, ASR-04.

---

## 6. Do not credit a new control with an old control's work

**Observed.** A measurement of a new control's effectiveness initially showed a
misleading result, because half the test cases targeted actions that an
*existing, unrelated* control already blocked. The new control appeared to
account for improvements it had nothing to do with.

**Why it generalizes.** Controls compose, which makes attribution hard and
flattering numbers easy. If you measure a control on a population where
something else is already stopping the attack, you measure the stack, not the
control — and you will believe the new thing is load-bearing when it is not.
The day you remove or weaken the *old* control, the number does not move and
nobody understands why.

**Do.** Measure a control where it is the **sole** thing standing between the
attack and the outcome. Report other populations separately as defence-in-depth,
with their own before/after. If a cohort shows no change because it was already
covered, say so explicitly — that is a real and useful finding, not a failure.

**Maps to.** ASR-03, ASR-09, LRN-01.

---

## 7. A classifier that nothing feeds is not a control

**Observed.** A provenance-tracking control depends on every content source
declaring what it is. Sources that do not declare themselves default to the
benign classification. The control can therefore be fully installed, fully
tested, and completely inert — and every check short of "did any source
actually declare itself?" still reports green.

**Why it generalizes.** Any control that classifies inputs has a default, and
the default applies to everything nobody remembered to wire up. Unit tests pass
(the logic is right), integration tests pass (the wiring you built is right),
and the paths you forgot are silent — because silence is what "no untrusted
input observed" looks like.

**Do.** Make "is anything at all being classified?" an explicit, monitored
check, separate from "is the classifier correct?". Query the classifier's own
records for evidence that the interesting class has *ever* been observed in
production. Zero occurrences of the class the control exists to catch is an
alert, not a clean bill.

**Maps to.** ING-01, OBS-01.

---

## 8. Prefer structural guarantees to procedural ones

**Observed.** The §7 problem — "every source must declare itself" — was solved
by auditing every caller. That works until someone adds a new one.

It stopped being a procedural obligation when a **default-deny egress control**
was placed in front of the same paths. Traffic cannot leave without matching an
allowlist entry, and every entry declares what class of content it returns. An
undeclared source is no longer mis-classified; it does not happen.

**Why it generalizes.** A procedural guarantee ("everyone must remember to X")
degrades with every new contributor and every deadline. A structural one ("X is
impossible to skip because the path does not exist without it") holds. Where
two controls are adjacent, check whether one can make the other's obligation
structural — it is often nearly free and it removes an entire class of drift.

**Do.** When a control depends on callers doing something, ask what would have
to be true for callers to be *unable* to skip it. Then ask whether an existing
chokepoint already sits there.

**Maps to.** ACT-04, ING-01, IDA-04.

---

## 9. Provenance survives obfuscation; content inspection does not

**Observed.** In an injection eval, payload families included base64-encoded and
homoglyph-substituted variants. These are specifically designed to defeat
inspection of *what the content says*. Against a control that only asks *where
the content came from*, they failed identically to the plain-text variants —
because provenance does not read the payload.

**Why it generalizes.** Content inspection is an arms race with an adversary
who can re-encode indefinitely. Origin is a property of the transport, not the
bytes, and the attacker does not control it.

The trade is real and worth stating: origin tracking is **coarse**. It cannot
tell you which sentence was malicious, so it taints whole sessions and produces
false positives — one retrieved page constrains everything that follows.
Accepting that imprecision is what buys immunity to obfuscation. Do not try to
recover the precision by adding content inspection back on top; you will
reintroduce the arms race and the false-positive rate.

**Maps to.** ING-01, ING-02, ING-07.

---

## 10. Untrusted content reaches durable state, and waits

**Observed.** Session-scoped provenance tracking stops injected content from
acting within the session it arrived in. It does not stop that content being
written to durable memory, where a later, entirely clean session recalls it.

**Why it generalizes.** Any agent with persistent memory has a path from
"untrusted input today" to "trusted context next week". Controls scoped to a
turn or a session do not see it, because by the time it activates, the session
that observed the injection is gone.

**Do.** Propagate provenance to the **write path**: durable entries carry the
taint of the context that wrote them, and recalling a tainted entry taints the
reader. Three properties matter:

- **Sticky.** Taint must not lift because a later turn looks benign. That is
  precisely the sleeper's shape.
- **Monotonic per entry.** Rewriting a tainted entry from a clean context must
  not launder it. Retiring a poisoned entry is a delete, not an update.
- **Unstamped means tainted.** Entries predating the control have unproven
  provenance. Defaulting them to clean removes the control while leaving all of
  its machinery in place, which is the worst available outcome. Expect a noisy
  rollout against an existing corpus and plan for it; if you backfill, record
  who attested and on what basis, because it cannot be verified retroactively.

**Maps to.** ING-06, ING-02.

---

## 11. Shipping a control library is not deploying a control

**Observed.** Several controls were built, tested, and committed in backlog
order. Discovery against the running system found that none were deployed, and
that the live authorization surface differed from the one the controls assumed
— different function signature, no tier concept, and two verdicts where the
control expected three.

**Why it generalizes.** Backlog order is dependency order *between tickets*.
Deployment order is dependency order *between running components*, and the two
diverge as soon as anything is built ahead of what it attaches to. A control
with no call site is inventory.

The verdict-count mismatch is the subtle one and worth naming: an existing gate
with `deny | require_human` maps *almost* onto `deny | escalate`. But "escalate"
carries the meaning *a human authorisation would permit this*. If the existing
`require_human` is a hard stop with no path to proceed, then adopting it as the
escalation target silently converts every escalation into an outage — and a
provenance control that escalates on every retrieved page becomes unusable.
**Check what your escalation path actually does before routing a control into
it.**

**Do.** Land controls in *enforcement* order, not build order — the stop
mechanism before the things that need stopping. Prefer an adapter that lets a
new gate take over incrementally over a single-change replacement of a live
authorization path. Run new gates in **shadow mode** first: evaluate, log the
divergence, let the old gate decide. That answers the only question that
matters at cutover — how many currently-allowed actions would the new gate
block — from real traffic rather than estimate.

**Maps to.** ASR-06, ACT-09, LRN-01.

---

## 12. Runbook preconditions need gates, not prose

**Observed.** An automated-integration runbook named its dependency in the
header and never provided a step to *verify* it. A competent operator followed
the discovery step, passed it, and got several steps into the procedure before
discovering the integration point did not exist.

**Why it generalizes.** This is the same failure as §7 one level up: a stated
requirement that nothing checks is a comment. It is worth noting that the
document in which this occurred was *specifically about* verifying every step
before advancing — the discipline was the subject matter and still did not
apply to its own preamble.

**Do.** Every precondition gets an executable check with an explicit stop
condition, and the check must interrogate the **running system**, not the
repository. "The library is importable" and "the library is wired into the live
call path" are different assertions, and only the second one matters.

**Maps to.** LRN-01, ASR-06.

---

## 13. Identity must survive to the enforcement point, not just the issuance point

**Observed.** Authority was issued correctly: every grant was minted against a
named principal rather than a bare API key, and that was accurately assessed as
a control in place. But the principal did not travel with the grant to the gate
that authorized the resulting action. The gate substituted a request
identifier — enough to correlate, not enough to attribute.

**Why it generalizes.** Any architecture that separates authorization (mint a
grant) from execution (spend it) can lose the actor in between. Attribution at
issuance answers *who asked*. Enforcement needs *who is acting*. Those are the
same question only if identity is deliberately threaded through, and nothing
fails loudly when it is not — the request still carries *an* identifier, so
logs look populated and correlation still works.

The non-obvious consequence is what it does to every control scoped **by**
principal. A principal-scoped stop that resolves identity at one chokepoint and
not another produces partial enforcement that presents as total: the model path
halts, the tool path keeps running. The control is not missing. It is present,
enabled, and matching nothing.

This also tends to be a single root cause presenting as several unrelated
defects — a scoped stop that half-works, a gate that cannot check grants, a
provenance tracker with no session key. Treating them separately produces three
partial fixes.

**Do.** Assert identity at the point of action, not only at the point of
authorization. Test principal-scoped controls at **every** chokepoint
independently — a drill that exercises one path passes while another is wide
open, and the scope-matching gap is invisible to a test that only checks the
control fires *somewhere*. For attribution controls, require evidence showing
the principal on the **action** record, not the authorization record.

**Maps to.** IDA-01, IDA-03, IDA-04, ACT-07.

---

## 14. A verdict with no destination degrades to the nearest one that exists

**Observed.** A gate designed around three verdicts — allow, deny, escalate —
was to be deployed onto an enforcement substrate that had two. Escalate had
nowhere to land, so it would have collapsed into deny.

Separately and more interestingly: the human-approval mechanism that *should*
have been escalate's destination did exist, was working, and was correctly
assessed as in place. It was simply not reachable from the gate. Two different
failures that present identically.

**Why it generalizes.**

*Verdict collapse.* An unimplemented verdict does not error — it degrades to
the nearest implemented one, which for a safety control is usually the most
restrictive. That sounds like the safe direction and is not. A control that
escalates routinely becomes an outage once escalate means deny, and a control
that causes outages gets switched off. Failing safe into an unusable state is
how controls get removed.

*Unreachable mechanisms.* Assessments score controls **individually**. A control
can be genuinely in place for its own purpose and still be invisible to the
control that needs to call it. Every entry on the scorecard is accurate and the
composition does not work — individually correct, jointly misleading. This is
§7 one layer up: there, a classifier nothing fed; here, a mechanism nothing can
reach.

**Do.** Before deploying any gate, enumerate its verdict set and name the
concrete mechanism each verdict lands in. **A verdict with no named destination
is not implemented**, however well the gate that emits it is tested. Where one
control depends on another, make the evidence include the *invocation path*,
not merely both controls' existence — "we have an approval mechanism" and "the
gate can invoke the approval mechanism" are different claims and only the
second one composes.

Check the semantics too, not just the arity. An existing "requires human"
outcome that is a hard stop is not the same as an escalation that a human
authorization can convert into a completed action, even though both are
two-state and both block by default.

**Maps to.** POL-02, HUM-11, ACT-02, LRN-01.

---

## Reading these together

Ten of the fourteen are the same failure wearing different clothes: **the
control was fine and the surrounding truth was not**. Not invoked (§11, §12),
not durable (§4), not fed (§7), not reachable (§14), not carrying identity
(§13), not distinguishable from breakage (§1, §2, §3), not attributed
correctly (§6).

The practical consequence is that "we implemented control X" is not a
meaningful claim, and neither is a passing test suite. The claims worth making
are narrower and each needs its own evidence:

- it is **invoked** on the live path — verified against the running system
- it is **durable** across replacement — verified by replacing the thing
- it is **fed** — verified by finding real records of the input class it exists
  to catch
- its failures are **distinguishable** — verified by breaking it deliberately
  and watching what the alerting says
- its effect is **attributable** — verified where it is the only control in play

Each of those is cheap to check once and expensive to assume. The ninety-minute
outage behind §1 through §4 was a single unverified assumption about an
environment variable.
