"""Example: Audit a DAML contract using the Ginie SDK.

Runs security audit and compliance analysis on raw DAML code.

Usage:
    python -m sdk.examples.audit_contract
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.client.ginie_client import GinieClient
from sdk.client.types import GinieAPIError

SAMPLE_DAML_CODE = """module Main where

import DA.Time

template BondContract
  with
    issuer : Party
    investor : Party
    faceValue : Decimal
    couponRate : Decimal
    maturityDate : Date
    isActive : Bool
  where
    signatory issuer
    observer investor

    ensure faceValue > 0.0 && couponRate > 0.0

    choice AcceptBond : ContractId BondContract
      controller investor
      do
        return self

    choice TransferBond : ContractId BondContract
      with
        newInvestor : Party
      controller investor
      do
        create this with investor = newInvestor
"""


def main():
    client = GinieClient()

    print("=" * 60)
    print("  Ginie SDK — Security Audit Example")
    print("=" * 60)

    # Run full audit (security + compliance)
    print("\n[1] Running security audit...")
    try:
        audit = client.run_audit(
            code=SAMPLE_DAML_CODE,
            contract_name="BondContract",
            compliance_profile="generic",
        )
    except GinieAPIError as e:
        print(f"    ERROR: {e}")
        return

    print(f"\n  Audit Success:    {audit.success}")
    print(f"  Security Score:   {audit.security_score}/100")
    print(f"  Compliance Score: {audit.compliance_score}/100")
    print(f"  Enterprise Score: {audit.enterprise_score}/100")
    print(f"  Deploy Gate:      {'PASS' if audit.deploy_gate else 'FAIL'}")
    print(f"  Findings Count:   {audit.findings_count}")

    if audit.executive_summary:
        print(f"\n  Executive Summary:")
        for key, val in audit.executive_summary.items():
            print(f"    {key}: {val}")

    # Run compliance against specific profile
    print("\n" + "-" * 60)
    print("\n[2] Running NIST 800-53 compliance check...")
    try:
        compliance = client.run_compliance(
            code=SAMPLE_DAML_CODE,
            contract_name="BondContract",
            profile="nist-800-53",
        )
    except GinieAPIError as e:
        print(f"    ERROR: {e}")
        return

    print(f"\n  Compliance Score: {compliance.compliance_score}/100")
    print(f"  Profile:          {compliance.profile}")

    if compliance.executive_summary:
        print(f"\n  Compliance Summary:")
        for key, val in compliance.executive_summary.items():
            if isinstance(val, str):
                print(f"    {key}: {val[:100]}")
            else:
                print(f"    {key}: {val}")

    # List available profiles
    print("\n" + "-" * 60)
    print("\n[3] Available compliance profiles:")
    try:
        profiles = client.list_compliance_profiles()
        for name in profiles.get("profiles", []):
            desc = profiles.get("descriptions", {}).get(name, "")
            print(f"    - {name}: {desc}")
    except GinieAPIError as e:
        print(f"    ERROR: {e}")

    print("\n" + "=" * 60)
    client.close()


if __name__ == "__main__":
    main()
