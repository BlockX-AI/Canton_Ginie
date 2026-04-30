"""Badge system for Ginie achievements.

Badges are awarded based on user actions (contract generation, deployment,
etc.). Uses an idempotent award mechanism: calling award_badge multiple
times for the same (user, badge) is a no-op.
"""

from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy.exc import IntegrityError

from db.session import get_db_session
from db.models import Badge, UserBadge, EmailAccount, JobHistory, DeployedContract

logger = structlog.get_logger()


# Default badge catalog — seeded into DB on startup.
DEFAULT_BADGES = [
    # Milestone: account creation & contract counts
    {
        "slug": "newcomer",
        "name": "Newcomer",
        "description": "Welcome to Ginie Canton!",
        "icon": "Sprout",
        "color": "#10b981",
        "category": "milestone",
        "criteria_type": "signup",
        "criteria_value": 1,
        "rarity": "common",
        "xp_reward": 5,
    },
    {
        "slug": "first_contract",
        "name": "First Contract",
        "description": "Generated your first Daml contract",
        "icon": "Sparkles",
        "color": "#a3e635",
        "category": "milestone",
        "criteria_type": "contract_count",
        "criteria_value": 1,
        "rarity": "common",
        "xp_reward": 10,
    },
    {
        "slug": "active_builder",
        "name": "Active Builder",
        "description": "Generated 5 contracts",
        "icon": "Zap",
        "color": "#eab308",
        "category": "milestone",
        "criteria_type": "contract_count",
        "criteria_value": 5,
        "rarity": "common",
        "xp_reward": 25,
    },
    {
        "slug": "canton_architect",
        "name": "Canton Architect",
        "description": "Generated 10 contracts",
        "icon": "Building2",
        "color": "#f97316",
        "category": "milestone",
        "criteria_type": "contract_count",
        "criteria_value": 10,
        "rarity": "rare",
        "xp_reward": 50,
    },
    {
        "slug": "power_user",
        "name": "Power User",
        "description": "Generated 25 contracts",
        "icon": "Rocket",
        "color": "#ec4899",
        "category": "milestone",
        "criteria_type": "contract_count",
        "criteria_value": 25,
        "rarity": "rare",
        "xp_reward": 100,
    },
    {
        "slug": "canton_master",
        "name": "Canton Master",
        "description": "Generated 50 contracts",
        "icon": "Gem",
        "color": "#8b5cf6",
        "category": "milestone",
        "criteria_type": "contract_count",
        "criteria_value": 50,
        "rarity": "epic",
        "xp_reward": 250,
    },
    {
        "slug": "canton_legend",
        "name": "Canton Legend",
        "description": "Generated 100 contracts",
        "icon": "Trophy",
        "color": "#facc15",
        "category": "milestone",
        "criteria_type": "contract_count",
        "criteria_value": 100,
        "rarity": "legendary",
        "xp_reward": 500,
    },
    # Deployment milestones
    {
        "slug": "first_deploy",
        "name": "First Deployment",
        "description": "Successfully deployed a contract to Canton",
        "icon": "Upload",
        "color": "#06b6d4",
        "category": "milestone",
        "criteria_type": "deploy_count",
        "criteria_value": 1,
        "rarity": "common",
        "xp_reward": 15,
    },
    {
        "slug": "sharpshooter",
        "name": "Sharpshooter",
        "description": "10 successful deployments",
        "icon": "Target",
        "color": "#ef4444",
        "category": "quality",
        "criteria_type": "deploy_count",
        "criteria_value": 10,
        "rarity": "rare",
        "xp_reward": 75,
    },
    # Special
    {
        "slug": "early_adopter",
        "name": "Early Adopter",
        "description": "Joined during launch month",
        "icon": "Crown",
        "color": "#f59e0b",
        "category": "special",
        "criteria_type": "special",
        "criteria_value": 0,
        "rarity": "legendary",
        "xp_reward": 100,
    },
]


def seed_badges() -> int:
    """Insert default badges into the catalog. Idempotent.
    
    Returns number of new badges added.
    """
    added = 0
    try:
        with get_db_session() as session:
            for b in DEFAULT_BADGES:
                existing = session.query(Badge).filter_by(slug=b["slug"]).first()
                if existing:
                    # Update metadata (but don't touch earned badges)
                    for k, v in b.items():
                        setattr(existing, k, v)
                else:
                    session.add(Badge(**b))
                    added += 1
            logger.info("Badge catalog seeded", added=added, total=len(DEFAULT_BADGES))
    except Exception as e:
        logger.exception("Failed to seed badges", error=str(e))
    return added


def _award_badge_internal(session, account_id: int, slug: str) -> Optional[UserBadge]:
    """Award a badge if not already earned. Returns the UserBadge or None."""
    badge = session.query(Badge).filter_by(slug=slug).first()
    if not badge:
        return None
    
    existing = session.query(UserBadge).filter_by(
        account_id=account_id, badge_id=badge.id
    ).first()
    if existing:
        return None  # Already has it
    
    ub = UserBadge(
        account_id=account_id,
        badge_id=badge.id,
        earned_at=datetime.now(timezone.utc),
    )
    session.add(ub)
    
    # Award XP
    account = session.query(EmailAccount).filter_by(id=account_id).first()
    if account and badge.xp_reward:
        account.xp = (account.xp or 0) + badge.xp_reward
    
    try:
        session.flush()
        logger.info("Badge awarded", account_id=account_id, slug=slug, xp=badge.xp_reward)
        return ub
    except IntegrityError:
        session.rollback()
        return None


def award_badge(email: str, slug: str) -> bool:
    """Award a specific badge to a user by email (idempotent)."""
    email = email.strip().lower()
    try:
        with get_db_session() as session:
            account = session.query(EmailAccount).filter_by(email=email).first()
            if not account:
                return False
            ub = _award_badge_internal(session, account.id, slug)
            return ub is not None
    except Exception as e:
        logger.exception("Failed to award badge", email=email, slug=slug, error=str(e))
        return False


def check_and_award_badges(email: str) -> List[str]:
    """Check all criteria-based badges and award any newly earned ones.
    
    Returns list of newly-awarded badge slugs. Safe to call after every
    contract generation / deployment, and also periodically for backfill.
    """
    email = email.strip().lower()
    newly_awarded: List[str] = []
    
    try:
        with get_db_session() as session:
            account = session.query(EmailAccount).filter_by(email=email).first()
            if not account:
                return []
            
            # Count contracts (by user_email in job_history)
            contract_count = session.query(JobHistory).filter(
                JobHistory.user_email == email,
                JobHistory.status == "complete",
            ).count()
            
            # Count successful deployments
            deploy_count = session.query(DeployedContract).filter(
                DeployedContract.user_email == email,
            ).count()
            
            # Iterate through all badges and check criteria
            badges = session.query(Badge).all()
            for badge in badges:
                awarded = False
                if badge.criteria_type == "signup":
                    # Every registered user gets the signup badge
                    awarded = True
                elif badge.criteria_type == "contract_count" and contract_count >= badge.criteria_value:
                    awarded = True
                elif badge.criteria_type == "deploy_count" and deploy_count >= badge.criteria_value:
                    awarded = True
                
                if awarded:
                    ub = _award_badge_internal(session, account.id, badge.slug)
                    if ub:
                        newly_awarded.append(badge.slug)
    except Exception as e:
        logger.exception("Failed to check badges", email=email, error=str(e))
    
    return newly_awarded


def backfill_all_user_badges() -> dict:
    """Run check_and_award_badges for every registered user.
    
    Useful after deploying badge logic changes so existing users get caught
    up on XP and badges they should have earned.
    """
    stats = {"users": 0, "newly_awarded": 0}
    try:
        with get_db_session() as session:
            emails = [row[0] for row in session.query(EmailAccount.email).all()]
        for email in emails:
            stats["users"] += 1
            stats["newly_awarded"] += len(check_and_award_badges(email))
        logger.info("Badge backfill complete", **stats)
    except Exception as e:
        logger.exception("Backfill failed", error=str(e))
    return stats


def get_leaderboard(limit: int = 100) -> List[dict]:
    """Return ranked list of users for the leaderboard.
    
    Ranks by XP descending, with deploy_count and contract_count as
    tie-breakers. Includes profile picture, display name, level, badge
    count, and recent badges.
    """
    with get_db_session() as session:
        accounts = session.query(EmailAccount).order_by(EmailAccount.xp.desc().nullslast()).limit(limit).all()
        results = []
        for acc in accounts:
            contract_count = session.query(JobHistory).filter(
                JobHistory.user_email == acc.email,
                JobHistory.status == "complete",
            ).count()
            deploy_count = session.query(DeployedContract).filter(
                DeployedContract.user_email == acc.email,
            ).count()
            badge_count = session.query(UserBadge).filter_by(account_id=acc.id).count()

            # Top 3 most recent badges for display
            recent_badges = (
                session.query(UserBadge, Badge)
                .join(Badge, UserBadge.badge_id == Badge.id)
                .filter(UserBadge.account_id == acc.id)
                .order_by(UserBadge.earned_at.desc())
                .limit(3)
                .all()
            )

            xp = acc.xp or 0
            results.append({
                "display_name": acc.display_name or (acc.email.split("@")[0] if acc.email else "user"),
                "profile_picture_url": acc.profile_picture_url,
                "xp": xp,
                "level": _level_from_xp(xp),
                "badge_count": badge_count,
                "contract_count": contract_count,
                "deploy_count": deploy_count,
                "rank_tier": _rank_tier(xp, contract_count, deploy_count),
                "recent_badges": [
                    {
                        "slug": b.slug,
                        "name": b.name,
                        "icon": b.icon,
                        "color": b.color,
                        "rarity": b.rarity,
                    }
                    for _ub, b in recent_badges
                ],
                "member_since": acc.created_at.isoformat() if acc.created_at else None,
            })
        # Final sort by xp desc, deploy_count desc, contract_count desc
        results.sort(key=lambda r: (-r["xp"], -r["deploy_count"], -r["contract_count"]))
        return results


def _rank_tier(xp: int, contract_count: int, deploy_count: int) -> str:
    """Categorise user into a trust tier based on activity."""
    if deploy_count >= 25 or xp >= 500:
        return "ARCHITECT"
    if deploy_count >= 10 or xp >= 200:
        return "BUILDER"
    if deploy_count >= 1 or contract_count >= 1:
        return "SIGNER"
    return "NEWCOMER"


def get_user_badges(email: str) -> List[dict]:
    """Get all badges earned by a user, with badge metadata."""
    email = email.strip().lower()
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email).first()
        if not account:
            return []
        
        results = (
            session.query(UserBadge, Badge)
            .join(Badge, UserBadge.badge_id == Badge.id)
            .filter(UserBadge.account_id == account.id)
            .order_by(UserBadge.earned_at.desc())
            .all()
        )
        
        return [
            {
                "slug": badge.slug,
                "name": badge.name,
                "description": badge.description,
                "icon": badge.icon,
                "color": badge.color,
                "category": badge.category,
                "rarity": badge.rarity,
                "xp_reward": badge.xp_reward,
                "earned_at": ub.earned_at.isoformat() if ub.earned_at else None,
            }
            for ub, badge in results
        ]


def get_user_stats(email: str) -> dict:
    """Get user XP, level, badge count, contract count."""
    email = email.strip().lower()
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email).first()
        if not account:
            return {}
        
        badge_count = session.query(UserBadge).filter_by(account_id=account.id).count()
        contract_count = session.query(JobHistory).filter(
            JobHistory.user_email == email,
            JobHistory.status == "complete",
        ).count()
        deploy_count = session.query(DeployedContract).filter(
            DeployedContract.user_email == email,
        ).count()
        
        xp = account.xp or 0
        level = _level_from_xp(xp)
        
        return {
            "email": account.email,
            "display_name": account.display_name,
            "profile_picture_url": account.profile_picture_url,
            "xp": xp,
            "level": level,
            "badge_count": badge_count,
            "contract_count": contract_count,
            "deploy_count": deploy_count,
            "member_since": account.created_at.isoformat() if account.created_at else None,
        }


def list_all_badges() -> List[dict]:
    """Get the full badge catalog (unearned included)."""
    with get_db_session() as session:
        badges = session.query(Badge).order_by(Badge.category, Badge.criteria_value).all()
        return [
            {
                "slug": b.slug,
                "name": b.name,
                "description": b.description,
                "icon": b.icon,
                "color": b.color,
                "category": b.category,
                "criteria_type": b.criteria_type,
                "criteria_value": b.criteria_value,
                "rarity": b.rarity,
                "xp_reward": b.xp_reward,
            }
            for b in badges
        ]


def _level_from_xp(xp: int) -> int:
    """Simple level formula: level = floor(sqrt(xp / 50)) + 1."""
    import math
    return int(math.sqrt(max(xp, 0) / 50)) + 1
