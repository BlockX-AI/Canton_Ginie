"""Load invite codes via API endpoint.

This script uses the admin API to generate and load invite codes.
Requires a valid JWT token from an authenticated user.
"""

import requests
import sys

API_URL = "https://api.ginie.xyz/api/v1"

# Pre-defined invite codes to load
INVITE_CODES = [
    "GS-A7K9-M2N4", "GS-B3L8-P5Q1", "GS-C6R2-T9W7", "GS-D1S4-V8X3", "GS-E9T6-Y2Z5",
    "GS-F4U1-A7B9", "GS-G8V3-C2D6", "GS-H5W7-E1F4", "GS-J2X9-G8H3", "GS-K6Y4-J5K1",
    "GS-L1Z8-M9N2", "GS-M7A3-P4Q6", "GS-N2B9-R1S8", "GS-P5C4-T7U3", "GS-Q8D1-V2W9",
    "GS-R3E6-X4Y7", "GS-S9F2-Z1A5", "GS-T4G7-B8C3", "GS-U1H9-D2E6", "GS-V6J4-F7G1",
    "GS-W2K8-H3J9", "GS-X7L3-K5M2", "GS-Y1M6-N8P4", "GS-Z9N2-Q3R7", "GS-A4P5-S1T6",
    "GS-B8Q1-U9V2", "GS-C3R7-W4X8", "GS-D6S2-Y1Z9", "GS-E1T4-A5B3", "GS-F9U8-C7D2",
    "GS-G4V3-E6F1", "GS-H7W9-G2H8", "GS-J2X5-J4K7", "GS-K8Y1-L9M3", "GS-L3Z6-N2P5",
    "GS-M9A2-Q8R4", "GS-N4B7-S3T1", "GS-P1C9-U6V8", "GS-Q5D3-W2X7", "GS-R8E6-Y9Z1",
    "GS-S2F4-A3B9", "GS-T7G1-C8D5", "GS-U3H6-E2F4", "GS-V9J2-G7H1", "GS-W4K8-J3K6",
    "GS-X1L5-M9N7", "GS-Y6M2-P4Q8", "GS-Z3N9-R1S5", "GS-A8P4-T6U2", "GS-B2Q7-V9W3",
]


def load_codes_directly():
    """Load codes directly into database (requires database access)."""
    import os
    import sys
    from pathlib import Path
    
    # Add backend to path
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))
    
    try:
        from db.session import get_db_session
        from db.models import InviteCode
        from datetime import datetime, timezone
        
        with get_db_session() as session:
            added = 0
            for code in INVITE_CODES:
                # Check if exists
                existing = session.query(InviteCode).filter_by(code=code).first()
                if not existing:
                    invite = InviteCode(
                        code=code,
                        created_by="system",
                        notes="Initial launch batch",
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(invite)
                    added += 1
            
            print(f"✅ Added {added} invite codes to database")
            print(f"📊 Total codes: {len(INVITE_CODES)}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("Loading invite codes directly into database...")
    load_codes_directly()
