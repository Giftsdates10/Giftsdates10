#!/usr/bin/env python3
"""
Make User B premium so they can access VIP profiles without unlocking.
"""
import os
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

def make_user_b_premium():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    users = db.users
    
    user_b_id = "53dfa3d9-aa85-47d5-a4ab-77015de07814"
    
    # Make User B premium
    result = users.update_one(
        {"id": user_b_id},
        {"$set": {
            "premium_until": "2030-01-01T00:00:00+00:00"
        }}
    )
    
    if result.modified_count > 0:
        print(f"✅ Made User B premium ({user_b_id})")
    else:
        print(f"⚠️ User B not found or already premium")

if __name__ == "__main__":
    make_user_b_premium()
