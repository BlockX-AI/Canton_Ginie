# M1 Acceptance-Criteria Update — Proposal PR

_This is the exact text to append to the M1 section of the Canton grant
proposal PR._

---

## Context

The Canton grant review raised five concrete gaps on our proposal (see
`DECLINE_PROPOSAL_ANALYSIS.md` or the reviewer comment thread). Four of them
are administrative and have already been closed:

1. ✅ External-reviewer-facing build command visible in README
   (`pip install canton-ginie`).
2. ✅ SDK published to PyPI as `canton-ginie` v0.1.0.
3. ✅ Tagged `v0.1.0` GitHub release with release notes.
4. ✅ Live `COMMUNITY_CONTRACTS.md` tracking external Contract IDs.

The fifth gap is structural: M1 today reads as a **creation milestone**
(we build X) rather than an **adoption milestone** (N external parties use X).
That is the single biggest reason comparable proposals (Canton Security
Framework, Canton Payment Streams) were declined despite having named
collaborators or interest letters.

---

## Amendment to add to M1

_Append the following bullet to the current M1 acceptance criteria list:_

> **External usage.** Minimum **10 contracts** deployed by parties outside
> the BlockX AI team using Ginie (via `pip install canton-ginie` or the
> hosted UI at `canton.ginie.xyz`), each with a real on-ledger
> `contract_id`, submitted via the [Community Contract issue
> template](https://github.com/BlockX-AI/Canton_Ginie/issues/new?template=community-contract.yml)
> and published in [`COMMUNITY_CONTRACTS.md`](https://github.com/BlockX-AI/Canton_Ginie/blob/main/COMMUNITY_CONTRACTS.md).
> At least 5 of the 10 must be on Canton DevNet (not sandbox) so the
> Contract IDs are independently verifiable on `cantonscan.com`.

---

## Why this specific wording

| Clause | Rationale |
|---|---|
| "Minimum 10 contracts" | Small enough to be achievable in the M1 window; large enough to distinguish "real usage" from "team demo." |
| "Outside the BlockX AI team" | Closes the reviewer's exact objection — prevents us from self-credentialing. |
| "via `pip install canton-ginie` or hosted UI" | Forces the distribution mechanism to actually work end-to-end for strangers. |
| "real on-ledger `contract_id`" | Not interest letters, not LOIs — actual on-chain evidence. |
| "submitted via Community Contract issue template" | Makes the submission process auditable and public; the reviewer can click through each one. |
| "Published in COMMUNITY_CONTRACTS.md" | Single authoritative list, in-repo, reviewable with the PR. |
| "≥5 on DevNet, verifiable on cantonscan.com" | Independent third-party verification — reviewer doesn't have to trust our infra. |

---

## Suggested delivery evidence

When M1 is delivered, the PR description should include:

- Link to [COMMUNITY_CONTRACTS.md](https://github.com/BlockX-AI/Canton_Ginie/blob/main/COMMUNITY_CONTRACTS.md)
  with ≥10 filled rows.
- Link to the [`canton-ginie` PyPI page](https://pypi.org/project/canton-ginie/)
  with the download count badge.
- Link to the tagged [`v0.1.0` GitHub release](https://github.com/BlockX-AI/Canton_Ginie/releases/tag/v0.1.0).
- At least 3 cantonscan.com URLs for devnet `contract_id` values pasted
  inline (the reviewer can click and verify immediately).

---

## Why this converts a declined proposal into a funded one

The two declined precedents hythloda cited:

- **Canton Security Framework** — no users named, no Contract IDs, no CI.
- **Canton Payment Streams** — 5 interested, 0 Contract IDs, CI unknown.

Both were "framework / capability / intent" proposals. Ginie already has
the deliverables those proposals lacked (live product, 51 commits, CI
passing, 5/5 deploy rate, 35 s latency). Adding the external-usage clause
above is what changes the M1 deliverable from _"we built a thing"_ to
_"N strangers used the thing we built, here are their Contract IDs."_
That reframing is the exact delta between declined and funded.
