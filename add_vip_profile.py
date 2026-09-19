#!/usr/bin/env python3
"""
Add minimal VIP profile to User A for VIP Scheduling testing.
"""
import os
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

def add_vip_profile():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    users = db.users
    
    user_a_id = "46310393-581a-40c8-834d-1c63f1fa26bc"
    
    # Add minimal VIP profile
    result = users.update_one(
        {"id": user_a_id},
        {"$set": {
            "vip": {
                "published": True,
                "post_mode": "integrated",  # Show on main profile
                "show_on_main": True,
                "photos": [],
                "private_photos": [],
                "services": [],
                "prices": {},
                "places": [],
                "availability": []
            }
        }}
    )
    
    if result.modified_count > 0:
        print(f"✅ Added minimal VIP profile to User A ({user_a_id})")
    else:
        print(f"⚠️ User A not found or already has VIP profile")

if __name__ == "__main__":
    add_vip_profile()
