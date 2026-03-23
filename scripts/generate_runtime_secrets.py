from __future__ import annotations

import argparse
import secrets


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate runtime secrets for swimdash admin auth.")
    parser.add_argument("--password", default="", help="Admin password. If omitted, generate a random one.")
    parser.add_argument("--password-length", type=int, default=18, help="Generated password length when --password is omitted.")
    args = parser.parse_args()

    password = args.password or secrets.token_urlsafe(max(args.password_length, 12))[: max(args.password_length, 12)]
    if not password:
        raise SystemExit("Admin password cannot be empty.")
    session_secret = secrets.token_urlsafe(48)

    print(f"SWIMDASH_ADMIN_PASSWORD={password}")
    print(f"SWIMDASH_ADMIN_SESSION_SECRET={session_secret}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
