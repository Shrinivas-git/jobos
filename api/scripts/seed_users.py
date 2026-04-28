#!/usr/bin/env python3
"""
Seed script to populate the users collection with manager/HOD users.
Mirrors the document structure written by /auth/me on first login.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db

SEED_USERS = [
    {"email": "manager@jobos.com",           "username": "manager",   "roles": ["manager"], "keycloak_id": "seed-manager"},
    {"email": "hod@jobos.com",               "username": "hod",       "roles": ["hod"],     "keycloak_id": "seed-hod"},
    {"email": "srinivassondur03@gmail.com",  "username": "shrinivas", "roles": ["manager"], "keycloak_id": "seed-shrinivas"},
]

def seed():
    db = get_db()
    for u in SEED_USERS:
        result = db.users.update_one(
            {"email": u["email"]},
            {"$set": {
                "email":        u["email"],
                "username":     u["username"],
                "roles":        u["roles"],
                "keycloak_id":  u["keycloak_id"],
                "last_seen":    datetime.utcnow(),
            }},
            upsert=True,
        )
        action = "inserted" if result.upserted_id else "updated"
        print(f"  [{action}] {u['email']} — roles: {u['roles']}")

    print(f"\nDone. {len(SEED_USERS)} users seeded.")

if __name__ == "__main__":
    seed()
