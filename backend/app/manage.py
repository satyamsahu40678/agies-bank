"""Explicit schema migration and safe analyst provisioning commands."""

import argparse
import getpass
from pathlib import Path
import re
import sys
from .query import select
from .config import ROOT, validate_configuration
from .db import SessionLocal
from .models import User
from .auth import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("migrate")
    sub.add_parser("verify-schema")
    sub.add_parser("reconcile")
    worker = sub.add_parser("worker")
    worker.add_argument("--max-jobs", type=int, default=50)
    sub.add_parser("migrate-legacy-sql")
    admin = sub.add_parser("create-analyst")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    validate_configuration()
    if args.action == "migrate":
        from .maintenance import initialize_store

        print(initialize_store())
    elif args.action == "verify-schema":
        from .maintenance import verify_schema

        print(verify_schema())
    elif args.action == "reconcile":
        from .maintenance import reconcile

        with SessionLocal() as db:
            report = reconcile(db)
        print(report)
        if not report["ok"]:
            raise SystemExit(1)
    elif args.action == "worker":
        from .services.automations import dispatch_due
        from .services.proactive import process_next

        dispatch_due()
        for _ in range(max(1, min(200, args.max_jobs))):
            if not process_next():
                break
    elif args.action == "migrate-legacy-sql":
        from alembic.config import Config
        from alembic import command

        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        print("Legacy SQL migrated. Application storage remains Firestore.")
    else:
        email = args.email.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            parser.error("Invalid email")
        password = (
            sys.stdin.readline().rstrip("\n")
            if args.password_stdin
            else getpass.getpass("New analyst password: ")
        )
        if len(password) < 12 or not all(
            re.search(pattern, password)
            for pattern in ["[a-z]", "[A-Z]", "[0-9]", r"[^A-Za-z0-9]"]
        ):
            parser.error(
                "Password must be at least 12 characters with upper/lowercase, a digit and a symbol"
            )
        with SessionLocal() as db:
            if db.scalar(select(User).where(User.email == email)):
                parser.error("Email already exists")
            db.add(
                User(
                    name=args.name[:100],
                    email=email,
                    role="analyst",
                    password_hash=hash_password(password),
                )
            )
            db.commit()
        print("Analyst created. Password was hashed and was not logged.")


if __name__ == "__main__":
    main()
