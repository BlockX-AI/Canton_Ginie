"""Generate initial batch of invite codes for Ginie Canton.

This script generates 50 invite codes and saves them to the database.
Run this once to bootstrap the invite-only system.

Usage:
    python scripts/generate_initial_invites.py
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set up minimal environment
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ginie")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


def main():
    try:
        from auth.invite_manager import create_invite_codes, get_invite_stats
        from db.session import init_db
        
        print("Initializing database...")
        init_db()
        
        print("\nGenerating 50 invite codes...")
        codes = create_invite_codes(
            count=50,
            created_by="system",
            notes="Initial batch for launch"
        )
        
        print(f"\n✅ Generated {len(codes)} invite codes:\n")
        print("=" * 60)
        
        # Print codes in a formatted way
        for i, code in enumerate(codes, 1):
            print(f"{i:2d}. {code}")
            if i % 10 == 0 and i < len(codes):
                print()
        
        print("=" * 60)
        
        # Show stats
        stats = get_invite_stats()
        print(f"\n📊 Invite Code Statistics:")
        print(f"   Total:     {stats['total']}")
        print(f"   Used:      {stats['used']}")
        print(f"   Available: {stats['available']}")
        
        print("\n✨ Invite codes saved to database!")
        print("\nYou can now use these codes for user signups.")
        print("Generate more codes via the API endpoint:")
        print("  POST /api/v1/admin/invite-codes/generate")
        
        # Also save to file for backup
        output_file = Path(__file__).parent.parent.parent / "GENERATED_INVITE_CODES.txt"
        with open(output_file, "w") as f:
            f.write("# Ginie Canton - Generated Invite Codes\n")
            f.write(f"# Generated: {len(codes)} codes\n")
            f.write("# Format: GS-XXXX-XXXX\n\n")
            for i, code in enumerate(codes, 1):
                f.write(f"{i:2d}. {code}\n")
        
        print(f"\n💾 Codes also saved to: {output_file}")
        
    except ImportError as e:
        print(f"\n❌ Error: Missing dependencies. Please install requirements first.")
        print(f"   {e}")
        print("\nRun: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
