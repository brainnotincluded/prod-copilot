"""Seed script to populate database with 20 test users with different roles.

Run with: python -m backend.app.db.seed_users
"""

import asyncio
import logging
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

from app.db.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database URL - adjust if needed
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/copilot"
)

# 20 Test users with different roles
TEST_USERS = [
    # Admin users (3)
    {"email": "admin@example.com", "name": "System Administrator", "role": "admin", "password": "admin123"},
    {"email": "manager@example.com", "name": "Product Manager", "role": "admin", "password": "manager123"},
    {"email": "lead@example.com", "name": "Team Lead", "role": "admin", "password": "lead123"},
    
    # Editor users (10)
    {"email": "developer1@example.com", "name": "John Developer", "role": "editor", "password": "dev123"},
    {"email": "developer2@example.com", "name": "Jane Coder", "role": "editor", "password": "dev123"},
    {"email": "analyst1@example.com", "name": "Data Analyst 1", "role": "editor", "password": "analyst123"},
    {"email": "analyst2@example.com", "name": "Data Analyst 2", "role": "editor", "password": "analyst123"},
    {"email": "engineer1@example.com", "name": "Backend Engineer", "role": "editor", "password": "engineer123"},
    {"email": "engineer2@example.com", "name": "Frontend Engineer", "role": "editor", "password": "engineer123"},
    {"email": "tester1@example.com", "name": "QA Tester 1", "role": "editor", "password": "tester123"},
    {"email": "tester2@example.com", "name": "QA Tester 2", "role": "editor", "password": "tester123"},
    {"email": "devops@example.com", "name": "DevOps Engineer", "role": "editor", "password": "devops123"},
    {"email": "architect@example.com", "name": "Solution Architect", "role": "editor", "password": "arch123"},
    
    # Viewer users (7)
    {"email": "viewer1@example.com", "name": "Business Viewer 1", "role": "viewer", "password": "viewer123"},
    {"email": "viewer2@example.com", "name": "Business Viewer 2", "role": "viewer", "password": "viewer123"},
    {"email": "stakeholder1@example.com", "name": "Stakeholder 1", "role": "viewer", "password": "stake123"},
    {"email": "stakeholder2@example.com", "name": "Stakeholder 2", "role": "viewer", "password": "stake123"},
    {"email": "guest1@example.com", "name": "Guest User 1", "role": "viewer", "password": "guest123"},
    {"email": "guest2@example.com", "name": "Guest User 2", "role": "viewer", "password": "guest123"},
    {"email": "readonly@example.com", "name": "Read Only User", "role": "viewer", "password": "readonly123"},
]


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


async def seed_users():
    """Seed the database with test users."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        created_count = 0
        skipped_count = 0
        
        for user_data in TEST_USERS:
            # Check if user already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info(f"User {user_data['email']} already exists, skipping")
                skipped_count += 1
                continue
            
            # Create new user
            new_user = User(
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
                name=user_data["name"],
                role=user_data["role"],
                is_active=1,
            )
            
            session.add(new_user)
            created_count += 1
            logger.info(f"Created user: {user_data['email']} ({user_data['role']})")
        
        await session.commit()
        logger.info(f"\nSeed complete: {created_count} users created, {skipped_count} skipped")
        logger.info(f"Total: {len(TEST_USERS)} test users in database")
        
        # Print summary by role
        result = await session.execute(select(User))
        all_users = result.scalars().all()
        
        admin_count = sum(1 for u in all_users if u.role == "admin")
        editor_count = sum(1 for u in all_users if u.role == "editor")
        viewer_count = sum(1 for u in all_users if u.role == "viewer")
        
        logger.info(f"\nRole distribution:")
        logger.info(f"  - Admin: {admin_count}")
        logger.info(f"  - Editor: {editor_count}")
        logger.info(f"  - Viewer: {viewer_count}")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_users())
