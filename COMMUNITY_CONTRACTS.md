# Community Contracts

**External Canton contracts deployed using [Ginie](https://canton.ginie.xyz) by
people outside the BlockX AI core team.**

This file is the canonical, auditable record of real-world usage of Ginie.
Every entry below is a `contract_id` produced on Canton sandbox or DevNet by
someone not on the core team, reachable on the respective explorer.

If you have deployed a contract with Ginie, please add it via a pull request
(see _How to submit_ below) or open a [Community Contract Submission
issue](https://github.com/BlockX-AI/Canton_Ginie/issues/new?template=community-contract.yml).

---

## Live submissions

| # | Date (UTC) | Who | Environment | Contract ID | Template | Explorer | Notes |
|---|---|---|---|---|---|---|---|
| — | _awaiting first external submission_ | — | — | — | — | — | — |

<!--
Example row (delete this comment once the first real entry is added):

| 1 | 2026-05-01 | [@canton-dev-alice](https://github.com/canton-dev-alice) | devnet | `0050e287c28a17a7100a5db4160fb47c…` | `Bond` | [cantonscan](https://cantonscan.com/contract/0050e287…) | Fixed-income demo contract |
-->

---

## Target for M1 delivery

As committed in the grant proposal M1 acceptance criteria:

> **External usage: minimum 10 contracts deployed by parties outside the
> BlockX AI team, with Contract IDs submitted with M1 delivery.**

Progress: **0 / 10** external contracts submitted.

---

## How to submit

### Option A — Quickest (hosted UI)

1. Go to [canton.ginie.xyz](https://canton.ginie.xyz).
2. Sign in (generates an Ed25519 key pair in your browser).
3. Describe any contract in plain English ("Create a bond contract between
   issuer and investor, 5% annual coupon…").
4. When deployment succeeds, copy the `contract_id` shown on the result page.
5. Submit it via one of:
   - **Issue template:**
     [Create a Community Contract issue](https://github.com/BlockX-AI/Canton_Ginie/issues/new?template=community-contract.yml).
     The maintainers will append it here.
   - **Direct PR:** Add a row to the table above and open a pull request.

### Option B — SDK (for developers)

```bash
pip install canton-ginie
```

```python
from ginie import GinieClient

client = GinieClient(base_url="https://api.ginie.xyz/api/v1")
result = client.full_pipeline(
    "Escrow contract between buyer and seller, released on dual confirmation"
)
print(result.contract_id)
print(result.explorer_link)
```

Then submit the `contract_id` as in Option A.

### What we track per entry

- **Date (UTC)** — when you deployed.
- **Who** — your GitHub handle (or "anonymous" if you prefer).
- **Environment** — `sandbox`, `devnet`, or `mainnet`.
- **Contract ID** — the on-ledger identifier.
- **Template** — the contract type (`Bond`, `Escrow`, `Option`, …).
- **Explorer** — a verifiable link on [cantonscan.com](https://cantonscan.com)
  (devnet/mainnet) or a self-hosted screenshot (sandbox).
- **Notes** — any short context (use case, which prompt, etc.).

### Privacy

- You control what goes in "Notes". Do not include proprietary data.
- You may submit under a pseudonymous GitHub handle.
- Contract IDs on devnet/mainnet are already public by the nature of Canton's
  ledger; listing them here just makes them discoverable.

---

## License

All submissions are listed under the repository's Apache 2.0 license.
By submitting, you affirm the contract was deployed by you (or your team)
and that you consent to it being listed publicly.
