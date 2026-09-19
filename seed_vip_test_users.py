#!/usr/bin/env python3
"""
Seed test users for VIP Scheduling testing.
Creates User A (VIP with coins) and User B (requester with coins).
"""
import os
import sys
from pymongo import MongoClient
from datetime import datetime
import uuid
import bcrypt

# Load env
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

def seed_users():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    users = db.users
    
    # Generate unique emails
    timestamp = datetime.now().strftime("%H%M%S")
    email_a = f"vip_user_a_{timestamp}@test.com"
    email_b = f"requester_b_{timestamp}@test.com"
    
    # Hash passwords
    password = "TestPass123!"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    # User A - VIP with coins
    user_a_id = str(uuid.uuid4())
    user_a = {
        "id": user_a_id,
        "email": email_a,
        "password": hashed,
        "name": "VIP Alice",
        "gender": "female",
        "interested_in": "male",
        "age": 28,
        "country": "USA",
        "city": "New York",
        "coins": 5000,
        "withdrawable": 0,
        "escrow": 0,
        "vip_until": "2030-01-01T00:00:00+00:00",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # User B - Requester with coins
    user_b_id = str(uuid.uuid4())
    user_b = {
        "id": user_b_id,
        "email": email_b,
        "password": hashed,
        "name": "Bob Requester",
        "gender": "male",
        "interested_in": "female",
        "age": 32,
        "country": "USA",
        "city": "New York",
        "coins": 5000,
        "withdrawable": 0,
        "escrow": 0,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # Insert users
    users.insert_one(user_a)
    users.insert_one(user_b)
    
    print(f"✅ Created test users:")
    print(f"User A (VIP): {email_a} / {password}")
    print(f"  ID: {user_a_id}")
    print(f"  Coins: 5000, VIP until: 2030-01-01")
    print(f"\nUser B (Requester): {email_b} / {password}")
    print(f"  ID: {user_b_id}")
    print(f"  Coins: 5000")
    print(f"\n📋 Save these credentials for testing!")
    
    # Write to file for easy access
    with open("/app/vip_test_credentials.txt", "w") as f:
        f.write(f"User A (VIP):\n")
        f.write(f"  Email: {email_a}\n")
        f.write(f"  Password: {password}\n")
        f.write(f"  ID: {user_a_id}\n")
        f.write(f"  Coins: 5000\n")
        f.write(f"  VIP until: 2030-01-01\n\n")
        f.write(f"User B (Requester):\n")
        f.write(f"  Email: {email_b}\n")
        f.write(f"  Password: {password}\n")
        f.write(f"  ID: {user_b_id}\n")
        f.write(f"  Coins: 5000\n")
    
    return user_a_id, user_b_id, email_a, email_b, password

if __name__ == "__main__":
    try:
        seed_users()
    except Exception as e:
        print(f"❌ Error seeding users: {e}")
        sys.exit(1)
