"""Verify the deterministic static checker catches the exact bugs the
LLM audit missed in user job 90e08e60 (Invoice contract).

The contract in question:
  * `ApproveInvoice` does ``create this`` with no ``with`` clause -> no-op
  * `RejectInvoice` does ``archive self; return ()`` -> bare archive (allowed by name)
  * `PayInvoice` does ``archive self; return ()`` -> bare archive (NOT allowed)
  * `import DA.Date` is unused
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from security.static_checks import detect_static_findings  # noqa: E402


SAMPLE = '''module Main where

import DA.Time
import DA.Date

template Invoice
  with
    vendor : Party
    client : Party
    invoiceId : Text
    amount : Decimal
    issuedAt : Time
    dueDate : Date
    description : Text
  where
    signatory vendor
    observer client

    ensure vendor /= client
        && invoiceId /= ""
        && amount > 0.0

    choice ApproveInvoice : ContractId Invoice
      controller client
      do
        assertMsg "Invoice already approved" (vendor /= client)
        create this

    choice RejectInvoice : ()
      controller client
      do
        archive self
        return ()

    choice PayInvoice : ()
      controller client
      do
        now <- getTime
        assertMsg "Invoice is overdue" (toDateUTC now <= dueDate)
        archive self
        return ()
'''


GOOD_SAMPLE = '''module Main where

import DA.Time

template Invoice
  with
    vendor : Party
    client : Party
    status : Text
    amount : Decimal
  where
    signatory vendor, client
    ensure vendor /= client && amount > 0.0

    choice Approve : ContractId Invoice
      controller client
      do
        create this with status = "Approved"

    choice Reject : ()
      controller client
      do
        archive self

    choice Pay : ContractId PaidInvoice
      controller client
      do
        archive self
        create PaidInvoice with vendor; client; amount

template PaidInvoice
  with
    vendor : Party
    client : Party
    amount : Decimal
  where
    signatory vendor, client
'''


def _ids(findings):
    return sorted(f["id"] for f in findings)


def main() -> None:
    bad = detect_static_findings(SAMPLE)
    bad_ids = _ids(bad)

    # Expect:
    #  - DSV-016::ApproveInvoice (bare `create this`)
    #  - DSV-017::PayInvoice     (bare archive on a non-Reject/Cancel name)
    #  - DSV-018::DA.Date        (unused import)
    # Must NOT include:
    #  - DSV-017::RejectInvoice  (Reject is allow-listed)
    #  - DSV-018::DA.Time        (uses getTime / toDateUTC)
    assert "DSV-016::ApproveInvoice" in bad_ids, bad_ids
    assert "DSV-017::PayInvoice" in bad_ids, bad_ids
    assert "DSV-018::DA.Date" in bad_ids, bad_ids
    assert "DSV-017::RejectInvoice" not in bad_ids, (
        f"Reject choice should be allow-listed, got {bad_ids}"
    )
    assert "DSV-018::DA.Time" not in bad_ids, (
        f"DA.Time IS used; should not flag, got {bad_ids}"
    )

    # Severity sanity: the no-op state transition is HIGH (most important).
    sev_by_id = {f["id"]: f["severity"] for f in bad}
    assert sev_by_id["DSV-016::ApproveInvoice"] == "HIGH", sev_by_id
    assert sev_by_id["DSV-017::PayInvoice"] == "MEDIUM", sev_by_id
    assert sev_by_id["DSV-018::DA.Date"] == "LOW", sev_by_id

    print("BAD sample findings:")
    for f in bad:
        print(f"  [{f['severity']:6}] {f['id']:30}  {f['title']}")

    # The fixed version should produce zero findings from the three checks.
    good = detect_static_findings(GOOD_SAMPLE)
    good_ids = _ids(good)
    bad_in_good = [
        i for i in good_ids
        if i.startswith("DSV-016::") or i.startswith("DSV-017::Pay")
    ]
    assert not bad_in_good, f"GOOD sample should not trigger no-op / archive findings, got {good_ids}"

    print()
    print("GOOD sample findings (should be empty for DSV-016/017):", good_ids or "[]")
    print("static checks smoke OK")


if __name__ == "__main__":
    main()
