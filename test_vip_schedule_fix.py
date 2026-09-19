#!/usr/bin/env python3
"""
Test VIP Scheduling booking access fix and reschedule flow.
Tests that regular (non-premium, non-VIP) users can see and use the standalone
availability card on a VIP's profile.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")

def setup_test_users():
    """Create two test users: A (VIP) and B (REGULAR)"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    users = db["users"]
    
    # Generate unique emails
    suffix = uuid.uuid4().hex[:8]
    email_a = f"vip_user_{suffix}@example.com"
    email_b = f"regular_user_{suffix}@example.com"
    
    # Generate password hash
    import bcrypt
    password_hash = bcrypt.hashpw('TestPass123!'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # User A - VIP with availability
    user_a_id = str(uuid.uuid4())
    user_a = {
        "id": user_a_id,
        "email": email_a,
        "password": password_hash,
        "name": "Alice VIP",
        "age": 28,
        "gender": "female",
        "city": "New York",
        "country": "USA",
        "bio": "VIP user with availability",
        "coins": 5000,
        "withdrawable": 0,
        "escrow": 0,
        "vip_until": "2030-01-01T00:00:00+00:00",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "photos": []
    }
    
    # User B - REGULAR (no premium, no VIP, just coins)
    user_b_id = str(uuid.uuid4())
    user_b = {
        "id": user_b_id,
        "email": email_b,
        "password": password_hash,
        "name": "Bob Regular",
        "age": 30,
        "gender": "male",
        "city": "Los Angeles",
        "country": "USA",
        "bio": "Regular user",
        "coins": 5000,
        "withdrawable": 0,
        "escrow": 0,
        # NO premium_until or vip_until - this is the key part of the fix
        "created_at": datetime.utcnow().isoformat() + "Z",
        "photos": []
    }
    
    # Insert users
    users.delete_many({"email": {"$in": [email_a, email_b]}})
    users.insert_one(user_a)
    users.insert_one(user_b)
    
    print(f"✅ Created test users:")
    print(f"   User A (VIP): {email_a} / TestPass123! (ID: {user_a_id})")
    print(f"   User B (REGULAR): {email_b} / TestPass123! (ID: {user_b_id})")
    
    client.close()
    return {
        "user_a": {"email": email_a, "password": "TestPass123!", "id": user_a_id},
        "user_b": {"email": email_b, "password": "TestPass123!", "id": user_b_id}
    }

if __name__ == "__main__":
    print("Setting up test users for VIP Scheduling fix test...")
    users = setup_test_users()
    print("\nTest users ready. Run the Playwright test now.")
    print(f"\nUser A ID: {users['user_a']['id']}")
    print(f"User B ID: {users['user_b']['id']}")
