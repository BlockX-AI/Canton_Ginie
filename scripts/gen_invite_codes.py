"""Generate N unique invite codes in the GS-XXXX-XXXX format and emit:
  - INVITE_CODES_BATCH3.sql   (PostgreSQL INSERT statements)
  - INVITE_CODES_BATCH3.txt   (plain list, one per line)

Format: ``GS-AAAA-BBBB`` where A and B are uppercase alphanumeric (A-Z, 0-9).
Run from the repo root: ``python scripts/gen_invite_codes.py``
"""

from __future__ import annotations

import secrets
import string
from pathlib import Path

COUNT = 100
ALPHABET = string.ascii_uppercase + string.digits
REPO_ROOT = Path(__file__).resolve().parent.parent


def make_code() -> str:
    a = "".join(secrets.choice(ALPHABET) for _ in range(4))
    b = "".join(secrets.choice(ALPHABET) for _ in range(4))
    return f"GS-{a}-{b}"


def main() -> None:
    codes: set[str] = set()
    while len(codes) < COUNT:
        codes.add(make_code())
    ordered = sorted(codes)

    txt_path = REPO_ROOT / "INVITE_CODES_BATCH3.txt"
    sql_path = REPO_ROOT / "INVITE_CODES_BATCH3.sql"

    txt_path.write_text("\n".join(ordered) + "\n", encoding="utf-8")

    lines = [
        f"-- Batch 3: {COUNT} additional invite codes (Ginie)",
        "-- Run on Railway PostgreSQL. Idempotent via ON CONFLICT (code) DO NOTHING.",
        "",
        "INSERT INTO invite_codes (code, created_by, created_at, used, used_by_email, used_at) VALUES",
    ]
    rows = [
        f"  ('{c}', 'admin', NOW(), 0, NULL, NULL)" for c in ordered
    ]
    lines.append(",\n".join(rows))
    lines.append("ON CONFLICT (code) DO NOTHING;")
    sql_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(ordered)} codes to:\n  {txt_path}\n  {sql_path}")


if __name__ == "__main__":
    main()
