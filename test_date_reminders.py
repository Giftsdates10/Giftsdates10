#!/usr/bin/env python3
"""
Test for GiftsDates automatic date reminders feature
Tests the _date_lifecycle_loop that runs every 60 seconds and sends reminders
at 24h, 3h, 1h, 30m, start, and end windows.
"""
import requests
import json
from datetime import datetime, timedelta, timezone
import sys
import time
import uuid
from pymongo import MongoClient

# Base URL from frontend/.env
BASE_URL = "https://login-vault-31.preview.emergentagent.com/api"

# MongoDB connection
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

def log(msg):
    print(f"[TEST] {msg}")

def register_user(email, password, name, age=25):
    """Register a new user and return token + user data"""
    payload = {
        "email": email,
        "password": password,
        "name": name,
        "age": age,
        "gender": "female",
        "interested_in": "male",
        "city": "TestCity",
        "country": "TestCountry"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    if resp.status_code != 200:
        log(f"❌ Registration failed for {email}: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json()
    return data["token"], data["user"]

def get_notifications(token):
    """Get notifications for a user"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/notifications", headers=headers)
    if resp.status_code != 200:
        log(f"❌ Failed to get notifications: {resp.status_code} {resp.text}")
        return None
    return resp.json()

def insert_fake_date(inviter_id, recipient_id, scheduled_start_minutes_from_now=20):
    """Insert a fake confirmed date into MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Calculate scheduled_start (20 minutes from now in UTC)
    now = datetime.now(timezone.utc)
    scheduled_start = now + timedelta(minutes=scheduled_start_minutes_from_now)
    scheduled_end = scheduled_start + timedelta(hours=3)
    
    date_id = str(uuid.uuid4())
    date_doc = {
        "id": date_id,
        "inviter_id": inviter_id,
        "recipient_id": recipient_id,
        "status": "DATE_CONFIRMED",
        "location": {
            "venue": "Test Cafe",
            "scheduled_start": scheduled_start.isoformat(),
            "scheduled_end": scheduled_end.isoformat()
        },
        "reminders": {},  # Empty, so m30 reminder is due
        "coins": 200,
        "total_hold": 200,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    result = db.dates.insert_one(date_doc)
    log(f"✅ Inserted fake date document: {date_id}")
    log(f"   scheduled_start: {scheduled_start.isoformat()}")
    log(f"   scheduled_end: {scheduled_end.isoformat()}")
    log(f"   Current time: {now.isoformat()}")
    log(f"   Time until start: {scheduled_start_minutes_from_now} minutes")
    
    return date_id, scheduled_start

def get_date_from_db(date_id):
    """Get date document from MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    return db.dates.find_one({"id": date_id}, {"_id": 0})

def get_notifications_from_db(user_id):
    """Get notifications from MongoDB for a user"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    return list(db.notifications.find({"user_id": user_id}, {"_id": 0}))

def cleanup_date(date_id):
    """Remove the test date from MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    result = db.dates.delete_one({"id": date_id})
    if result.deleted_count > 0:
        log(f"✅ Cleaned up test date: {date_id}")
    else:
        log(f"⚠️  Warning: Could not clean up date {date_id}")

def run_test():
    log("=" * 80)
    log("STARTING DATE REMINDERS TEST")
    log("=" * 80)
    
    # Step 1: Register two users (inviter and recipient)
    log("\n📝 Step 1: Registering test users...")
    timestamp = datetime.now().timestamp()
    
    inviter_token, inviter_user = register_user(
        f"inviter_{timestamp}@test.com",
        "password123",
        "Inviter User"
    )
    if not inviter_token:
        log("❌ Failed to register inviter user")
        return False
    
    recipient_token, recipient_user = register_user(
        f"recipient_{timestamp}@test.com",
        "password123",
        "Recipient User"
    )
    if not recipient_token:
        log("❌ Failed to register recipient user")
        return False
    
    log(f"✅ Registered inviter: {inviter_user['id']}")
    log(f"✅ Registered recipient: {recipient_user['id']}")
    
    # Step 2: Insert fake confirmed date with scheduled_start 20 minutes from now
    log("\n📅 Step 2: Inserting fake confirmed date (scheduled_start = 20 min from now)...")
    date_id, scheduled_start = insert_fake_date(inviter_user["id"], recipient_user["id"], 20)
    
    # Step 3: Wait for the lifecycle loop to run
    log("\n⏳ Step 3: Waiting for lifecycle loop to run...")
    log("   The _date_lifecycle_loop runs every 60 seconds (after initial 20s delay)")
    log("   Since scheduled_start is 20 min away, the 'm30' window is active")
    log("   (m30 window: start-30m <= now < start)")
    log("   Waiting 75 seconds to ensure the loop runs at least once...")
    
    # Wait 75 seconds to ensure the loop runs
    for i in range(75, 0, -5):
        log(f"   Waiting... {i} seconds remaining")
        time.sleep(5)
    
    log("✅ Wait complete")
    
    # Step 4: Verify the reminders.m30 flag is set
    log("\n🔍 Step 4: Verifying reminders.m30 flag in date document...")
    date_doc = get_date_from_db(date_id)
    
    if not date_doc:
        log(f"❌ FAIL: Date document not found: {date_id}")
        return False
    
    reminders = date_doc.get("reminders", {})
    log(f"   Date reminders: {json.dumps(reminders, indent=2)}")
    
    if not reminders.get("m30"):
        log("❌ FAIL: reminders.m30 flag is not set to True")
        log(f"   Expected: reminders.m30 = True")
        log(f"   Got: reminders.m30 = {reminders.get('m30')}")
        cleanup_date(date_id)
        return False
    
    log("✅ PASS: reminders.m30 flag is set to True")
    
    # Step 5: Verify both users have date_reminder notifications
    log("\n🔔 Step 5: Verifying date_reminder notifications for both users...")
    
    # Check inviter notifications
    log("\n   Checking inviter notifications...")
    inviter_notifications = get_notifications_from_db(inviter_user["id"])
    inviter_reminder_notifs = [n for n in inviter_notifications if n.get("type") == "date_reminder"]
    
    log(f"   Inviter has {len(inviter_reminder_notifs)} date_reminder notification(s)")
    if inviter_reminder_notifs:
        for notif in inviter_reminder_notifs:
            log(f"      - Title: {notif.get('title')}")
            log(f"        Body: {notif.get('body')}")
            log(f"        Data: {notif.get('data')}")
    
    if not inviter_reminder_notifs:
        log("❌ FAIL: Inviter has no date_reminder notifications")
        cleanup_date(date_id)
        return False
    
    # Verify notification content
    inviter_notif = inviter_reminder_notifs[0]
    if "30 minutes" not in inviter_notif.get("title", ""):
        log(f"❌ FAIL: Inviter notification title should mention '30 minutes'")
        log(f"   Got: {inviter_notif.get('title')}")
        cleanup_date(date_id)
        return False
    
    if inviter_notif.get("data", {}).get("date_id") != date_id:
        log(f"❌ FAIL: Inviter notification data.date_id mismatch")
        log(f"   Expected: {date_id}")
        log(f"   Got: {inviter_notif.get('data', {}).get('date_id')}")
        cleanup_date(date_id)
        return False
    
    log("✅ PASS: Inviter has correct date_reminder notification")
    
    # Check recipient notifications
    log("\n   Checking recipient notifications...")
    recipient_notifications = get_notifications_from_db(recipient_user["id"])
    recipient_reminder_notifs = [n for n in recipient_notifications if n.get("type") == "date_reminder"]
    
    log(f"   Recipient has {len(recipient_reminder_notifs)} date_reminder notification(s)")
    if recipient_reminder_notifs:
        for notif in recipient_reminder_notifs:
            log(f"      - Title: {notif.get('title')}")
            log(f"        Body: {notif.get('body')}")
            log(f"        Data: {notif.get('data')}")
    
    if not recipient_reminder_notifs:
        log("❌ FAIL: Recipient has no date_reminder notifications")
        cleanup_date(date_id)
        return False
    
    # Verify notification content
    recipient_notif = recipient_reminder_notifs[0]
    if "30 minutes" not in recipient_notif.get("title", ""):
        log(f"❌ FAIL: Recipient notification title should mention '30 minutes'")
        log(f"   Got: {recipient_notif.get('title')}")
        cleanup_date(date_id)
        return False
    
    if recipient_notif.get("data", {}).get("date_id") != date_id:
        log(f"❌ FAIL: Recipient notification data.date_id mismatch")
        log(f"   Expected: {date_id}")
        log(f"   Got: {recipient_notif.get('data', {}).get('date_id')}")
        cleanup_date(date_id)
        return False
    
    log("✅ PASS: Recipient has correct date_reminder notification")
    
    # Step 6: Verify no duplicate reminders
    log("\n🔒 Step 6: Verifying no duplicate reminders...")
    log("   Waiting another 65 seconds to see if loop runs again...")
    
    for i in range(65, 0, -5):
        log(f"   Waiting... {i} seconds remaining")
        time.sleep(5)
    
    # Check notifications again
    inviter_notifications_after = get_notifications_from_db(inviter_user["id"])
    inviter_reminder_notifs_after = [n for n in inviter_notifications_after if n.get("type") == "date_reminder"]
    
    recipient_notifications_after = get_notifications_from_db(recipient_user["id"])
    recipient_reminder_notifs_after = [n for n in recipient_notifications_after if n.get("type") == "date_reminder"]
    
    log(f"   Inviter now has {len(inviter_reminder_notifs_after)} date_reminder notification(s)")
    log(f"   Recipient now has {len(recipient_reminder_notifs_after)} date_reminder notification(s)")
    
    if len(inviter_reminder_notifs_after) > len(inviter_reminder_notifs):
        log("❌ FAIL: Duplicate m30 reminder sent to inviter")
        cleanup_date(date_id)
        return False
    
    if len(recipient_reminder_notifs_after) > len(recipient_reminder_notifs):
        log("❌ FAIL: Duplicate m30 reminder sent to recipient")
        cleanup_date(date_id)
        return False
    
    log("✅ PASS: No duplicate reminders sent (flag prevents re-send)")
    
    # Cleanup
    log("\n🧹 Cleaning up test data...")
    cleanup_date(date_id)
    
    # All tests passed
    log("\n" + "=" * 80)
    log("✅ ALL DATE REMINDER TESTS PASSED!")
    log("=" * 80)
    log("\nSummary:")
    log("  ✅ Date document's reminders.m30 flag set to True")
    log("  ✅ Inviter received date_reminder notification")
    log("  ✅ Recipient received date_reminder notification")
    log("  ✅ Notification titles mention '30 minutes'")
    log("  ✅ Notification data includes correct date_id")
    log("  ✅ No duplicate reminders sent (flag prevents re-send)")
    
    return True

if __name__ == "__main__":
    try:
        success = run_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
