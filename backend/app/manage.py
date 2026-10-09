"""Administrative local CLI; never exposes account creation over HTTP."""

import argparse, getpass
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from zoneinfo import ZoneInfo
from app.core.database import SessionLocal, engine
from app.core.security import hash_password, data_cipher
from app.models.people import Organization, User, Message
from app.models.entities import Meeting
from app.models.source_actions import SourceInbox
from app.models.email_actions import CommitmentEmail


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--organization", default="Action Labs")
    create.add_argument("--timezone", default="UTC")
    reset = sub.add_parser("set-password")
    reset.add_argument("--email", required=True)
    sub.add_parser("encrypt-existing")
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            if args.command == "encrypt-existing":
                if not data_cipher():
                    raise ValueError("Set DATA_ENCRYPTION_KEYS first")
                # Keyset batches avoid loading all raw content; resumable and rotation-safe.
                for model, field in (
                    (Message, "body"),
                    (Meeting, "transcript"),
                    (SourceInbox, "payload"),
                    (CommitmentEmail, "body_text"),
                ):
                    cursor = ""
                    while True:
                        rows = list(
                            db.scalars(
                                select(model)
                                .where(model.id > cursor)
                                .order_by(model.id)
                                .limit(100)
                            )
                        )
                        if not rows:
                            break
                        for row in rows:
                            flag_modified(row, field)
                        cursor = rows[-1].id
                        db.commit()
                print("Existing raw content encrypted with the current key")
                return
            email = args.email.strip().lower()
            if "@" not in email or len(email) > 200:
                raise ValueError("Enter a valid email")
            user = db.scalar(select(User).where(User.email == email))
            if args.command == "create-user":
                ZoneInfo(args.timezone)
                if user:
                    raise ValueError("User already exists; use set-password")
                if not 1 <= len(args.name.strip()) <= 120:
                    raise ValueError("Invalid name")
                if not 1 <= len(args.organization.strip()) <= 200:
                    raise ValueError("Invalid organization")
                org = db.scalar(
                    select(Organization).where(Organization.name == args.organization)
                )
                if not org:
                    org = Organization(name=args.organization)
                    db.add(org)
                    db.flush()
                user = User(
                    name=args.name.strip(),
                    email=email,
                    organization_id=org.id,
                    timezone=args.timezone,
                )
                db.add(user)
            if not user:
                raise ValueError("User not found")
            password = getpass.getpass("New password (12+ characters): ")
            if password != getpass.getpass("Confirm password: "):
                raise ValueError("Passwords do not match")
            user.password_hash = hash_password(password)
            from app.models.people import LoginSession
            from sqlalchemy import delete

            db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
            db.commit()
            print("Account saved; sign in using your email")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
