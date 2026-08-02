"""
One-off script to create the first administrator account.
Usage: python3 -m app.scripts.seed_admin --email admin@example.com --password 'Str0ngPass!' --name "Admin Name"
"""
import argparse
import sys

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.enums import UserRole, UserStatus


def main():
    parser = argparse.ArgumentParser(description="Create the first administrator user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--phone", required=False, default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == args.email.lower().strip()).first()
        if existing:
            print(f"A user with email {args.email} already exists (role={existing.role.value}).")
            sys.exit(1)

        admin = User(
            name=args.name,
            email=args.email.lower().strip(),
            phone=args.phone,
            password_hash=hash_password(args.password),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: {admin.email} (id={admin.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
