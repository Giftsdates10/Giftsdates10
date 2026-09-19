#!/usr/bin/env python3
"""
Backend API test for GiftsDates "Book a Date" features
Tests: 3 mandatory activities, 2.5-hour slots, 15-min buffer, activity selection, cancellation coin splits
"""
import requests
import json
from datetime import datetime, timedelta
import sys

# Base URL from frontend/.env
BASE_URL = "https://login-vault-31.preview.emergentagent.com/api"

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

def add_coins_directly(user_id, amount):
    """Add coins directly to MongoDB (simulating purchase)"""
    from pymongo import MongoClient
    mongo_url = "mongodb://localhost:27017"
    client = MongoClient(mongo_url)
    db = client["test_database"]
    result = db.users.update_one({"id": user_id}, {"$inc": {"coins": amount}})
    if result.modified_count > 0:
        log(f"✅ Added {amount} coins to user {user_id}")
    else:
        log(f"⚠️  Warning: Could not add coins to user {user_id} (modified_count={result.modified_count})")

def update_profile(token, updates):
    """Update user profile"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.patch(f"{BASE_URL}/auth/me", json=updates, headers=headers)
    if resp.status_code != 200:
        log(f"❌ Profile update failed: {resp.status_code} {resp.text}")
        return None
    return resp.json()

def book_date(token, target_id, venue, city, scheduled_at, coins, activities=None, local_time=None):
    """Book a date"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "target_id": target_id,
        "venue": venue,
        "city": city,
        "scheduled_at": scheduled_at,
        "coins": coins,
        "local_time": local_time
    }
    if activities is not None:
        payload["activities"] = activities
    resp = requests.post(f"{BASE_URL}/dates/book", json=payload, headers=headers)
    return resp

def get_dates(token):
    """Get all dates for user"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/dates", headers=headers)
    if resp.status_code != 200:
        return None
    return resp.json()

def get_availability(token, target_id):
    """Get availability for a profile"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/profiles/{target_id}/availability", headers=headers)
    return resp

def respond_to_date(token, booking_id, accept, selected_activity=None):
    """Accept or decline a date"""
    headers = {"Authorization": f"Bearer {token}"}
    params = {"accept": str(accept).lower()}
    if selected_activity:
        params["selected_activity"] = selected_activity
    resp = requests.post(f"{BASE_URL}/dates/respond/{booking_id}", params=params, headers=headers)
    return resp

def cancel_date(token, booking_id):
    """Cancel a date"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/dates/cancel/{booking_id}", headers=headers)
    return resp

def get_user_balance(token):
    """Get current user's coin balance"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if resp.status_code != 200:
        return None, None
    user = resp.json()
    return user.get("coins", 0), user.get("withdrawable", 0)

def run_tests():
    log("=" * 80)
    log("STARTING GIFTSDATES 'BOOK A DATE' BACKEND TESTS")
    log("=" * 80)
    
    # Register users
    log("\n📝 Registering test users...")
    target_token, target_user = register_user(
        f"target_{datetime.now().timestamp()}@test.com",
        "password123",
        "Target User"
    )
    if not target_token:
        log("❌ Failed to register target user")
        return False
    
    requester_a_token, requester_a_user = register_user(
        f"requester_a_{datetime.now().timestamp()}@test.com",
        "password123",
        "Requester A"
    )
    if not requester_a_token:
        log("❌ Failed to register requester A")
        return False
    
    requester_b_token, requester_b_user = register_user(
        f"requester_b_{datetime.now().timestamp()}@test.com",
        "password123",
        "Requester B"
    )
    if not requester_b_token:
        log("❌ Failed to register requester B")
        return False
    
    log(f"✅ Registered target: {target_user['id']}")
    log(f"✅ Registered requester A: {requester_a_user['id']}")
    log(f"✅ Registered requester B: {requester_b_user['id']}")
    
    # Add coins to requesters
    log("\n💰 Adding coins to requesters...")
    add_coins_directly(requester_a_user["id"], 1000)
    add_coins_directly(requester_b_user["id"], 1000)
    
    # Set target availability for tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    log(f"\n📅 Setting target availability for {tomorrow} 18:00-23:00...")
    availability_update = {
        "availability": [tomorrow],
        "availability_time": {"from": "18:00", "to": "23:00"}
    }
    updated = update_profile(target_token, availability_update)
    if not updated:
        log("❌ Failed to set availability")
        return False
    log("✅ Target availability set")
    
    # TEST 1: 3 MANDATORY ACTIVITIES
    log("\n" + "=" * 80)
    log("TEST 1: 3 MANDATORY ACTIVITIES")
    log("=" * 80)
    
    # Test 1a: Booking WITHOUT activities field should be REJECTED
    log("\n1a) Booking WITHOUT activities field...")
    scheduled_at = f"{tomorrow}T18:00:00Z"
    resp = book_date(requester_a_token, target_user["id"], "Test Venue", "Test City", 
                     scheduled_at, 400, activities=None, local_time="18:00")
    if resp.status_code == 400 and "ACTIVITIES_REQUIRED" in resp.text:
        log("✅ PASS: Booking without activities rejected with ACTIVITIES_REQUIRED")
    else:
        log(f"❌ FAIL: Expected 400 ACTIVITIES_REQUIRED, got {resp.status_code}: {resp.text}")
        return False
    
    # Test 1b: Booking with fewer than 3 activities should be REJECTED
    log("\n1b) Booking with only 2 activities...")
    resp = book_date(requester_a_token, target_user["id"], "Test Venue", "Test City",
                     scheduled_at, 400, activities=["Coffee", "Walk"], local_time="18:00")
    if resp.status_code == 400 and "ACTIVITIES_REQUIRED" in resp.text:
        log("✅ PASS: Booking with 2 activities rejected with ACTIVITIES_REQUIRED")
    else:
        log(f"❌ FAIL: Expected 400 ACTIVITIES_REQUIRED, got {resp.status_code}: {resp.text}")
        return False
    
    # Test 1c: Booking with exactly 3 activities should SUCCEED
    log("\n1c) Booking with exactly 3 activities at 18:00...")
    activities = ["Coffee & walk", "Rooftop cocktails", "Mini-golf"]
    resp = book_date(requester_a_token, target_user["id"], "Test Venue", "Test City",
                     scheduled_at, 400, activities=activities, local_time="18:00")
    if resp.status_code != 200:
        log(f"❌ FAIL: Booking with 3 activities failed: {resp.status_code} {resp.text}")
        return False
    
    booking_data = resp.json()
    booking_id_1 = booking_data["booking_id"]
    log(f"✅ PASS: Booking succeeded with status={booking_data['status']}, booking_id={booking_id_1}")
    
    # Verify the booking has 3 activities and selected_activity=null
    log("\n1d) Verifying booking has 3 activities stored and selected_activity=null...")
    dates = get_dates(requester_a_token)
    if not dates:
        log("❌ FAIL: Could not fetch dates")
        return False
    
    booking = None
    for b in dates.get("outgoing", []):
        if b["id"] == booking_id_1:
            booking = b
            break
    
    if not booking:
        log("❌ FAIL: Booking not found in dates list")
        return False
    
    if booking.get("activities") != activities:
        log(f"❌ FAIL: Activities mismatch. Expected {activities}, got {booking.get('activities')}")
        return False
    
    if booking.get("selected_activity") is not None:
        log(f"❌ FAIL: selected_activity should be null, got {booking.get('selected_activity')}")
        return False
    
    log("✅ PASS: Booking has 3 activities stored and selected_activity=null")
    
    # TEST 2: 2.5-HOUR SLOT
    log("\n" + "=" * 80)
    log("TEST 2: 2.5-HOUR SLOT (150 minutes)")
    log("=" * 80)
    
    log("\n2a) Verifying booking slot_from=18:00 and slot_to=20:30...")
    if booking.get("slot_from") != "18:00":
        log(f"❌ FAIL: slot_from should be 18:00, got {booking.get('slot_from')}")
        return False
    if booking.get("slot_to") != "20:30":
        log(f"❌ FAIL: slot_to should be 20:30, got {booking.get('slot_to')}")
        return False
    log("✅ PASS: Booking has slot_from=18:00 and slot_to=20:30 (2.5 hours)")
    
    log("\n2b) Checking GET /api/profiles/{target}/availability...")
    avail_resp = get_availability(requester_a_token, target_user["id"])
    if avail_resp.status_code != 200:
        log(f"❌ FAIL: Availability check failed: {avail_resp.status_code} {avail_resp.text}")
        return False
    
    avail_data = avail_resp.json()
    if avail_data.get("slot_hours") != 2.5:
        log(f"❌ FAIL: slot_hours should be 2.5, got {avail_data.get('slot_hours')}")
        return False
    if avail_data.get("buffer") != 15:
        log(f"❌ FAIL: buffer should be 15, got {avail_data.get('buffer')}")
        return False
    log("✅ PASS: Availability returns slot_hours=2.5 and buffer=15")
    
    log("\n2c) Verifying busy_slots shows 18:00-20:30 with lock_from~17:45 and lock_to~20:45...")
    busy_slots = avail_data.get("busy_slots", {}).get(tomorrow, [])
    if not busy_slots:
        log("❌ FAIL: No busy slots found for tomorrow")
        return False
    
    slot = busy_slots[0]
    if slot.get("from") != "18:00" or slot.get("to") != "20:30":
        log(f"❌ FAIL: Busy slot should be 18:00-20:30, got {slot.get('from')}-{slot.get('to')}")
        return False
    if slot.get("lock_from") != "17:45" or slot.get("lock_to") != "20:45":
        log(f"❌ FAIL: Lock should be 17:45-20:45, got {slot.get('lock_from')}-{slot.get('lock_to')}")
        return False
    log("✅ PASS: busy_slots correctly shows 18:00-20:30 with lock_from=17:45 and lock_to=20:45")
    
    # TEST 3: BUFFER GAP
    log("\n" + "=" * 80)
    log("TEST 3: 15-MINUTE BUFFER GAP")
    log("=" * 80)
    
    log("\n3) Requester B trying to book at 20:30 (immediately after first booking)...")
    scheduled_at_b = f"{tomorrow}T20:30:00Z"
    resp = book_date(requester_b_token, target_user["id"], "Test Venue 2", "Test City",
                     scheduled_at_b, 400, activities=["Activity 1", "Activity 2", "Activity 3"],
                     local_time="20:30")
    if resp.status_code == 400 and "SLOT_BUSY" in resp.text:
        log("✅ PASS: Booking at 20:30 rejected with SLOT_BUSY due to 15-min buffer")
    else:
        log(f"❌ FAIL: Expected 400 SLOT_BUSY, got {resp.status_code}: {resp.text}")
        return False
    
    # TEST 4: INVITEE SELECTS ACTIVITY ON ACCEPT
    log("\n" + "=" * 80)
    log("TEST 4: INVITEE SELECTS ACTIVITY ON ACCEPT")
    log("=" * 80)
    
    # Test 4a: Accept WITHOUT selected_activity should be REJECTED
    log("\n4a) Target accepting booking WITHOUT selected_activity...")
    resp = respond_to_date(target_token, booking_id_1, accept=True, selected_activity=None)
    if resp.status_code == 400 and "SELECT_ACTIVITY" in resp.text:
        log("✅ PASS: Accept without selected_activity rejected with SELECT_ACTIVITY")
    else:
        log(f"❌ FAIL: Expected 400 SELECT_ACTIVITY, got {resp.status_code}: {resp.text}")
        return False
    
    # Test 4b: Accept with activity NOT in the 3 options should be REJECTED
    log("\n4b) Target accepting with activity NOT in the 3 options...")
    resp = respond_to_date(target_token, booking_id_1, accept=True, selected_activity="Invalid Activity")
    if resp.status_code == 400 and "SELECT_ACTIVITY" in resp.text:
        log("✅ PASS: Accept with invalid activity rejected with SELECT_ACTIVITY")
    else:
        log(f"❌ FAIL: Expected 400 SELECT_ACTIVITY, got {resp.status_code}: {resp.text}")
        return False
    
    # Test 4c: Accept with one of the 3 exact activity strings should SUCCEED
    log("\n4c) Target accepting with valid activity from the 3 options...")
    resp = respond_to_date(target_token, booking_id_1, accept=True, selected_activity="Rooftop cocktails")
    if resp.status_code != 200:
        log(f"❌ FAIL: Accept with valid activity failed: {resp.status_code} {resp.text}")
        return False
    
    accept_data = resp.json()
    if accept_data.get("status") != "accepted":
        log(f"❌ FAIL: Status should be 'accepted', got {accept_data.get('status')}")
        return False
    if accept_data.get("selected_activity") != "Rooftop cocktails":
        log(f"❌ FAIL: selected_activity should be 'Rooftop cocktails', got {accept_data.get('selected_activity')}")
        return False
    log("✅ PASS: Accept succeeded with status=accepted and selected_activity saved")
    
    # TEST 5: CANCELLATION COIN SPLIT - Scenario A (inviter cancels)
    log("\n" + "=" * 80)
    log("TEST 5: CANCELLATION COIN SPLIT - Scenario A (inviter cancels)")
    log("=" * 80)
    
    # Create a fresh booking for cancellation test
    log("\n5a) Creating fresh booking for cancellation test...")
    future_day = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    # Update target availability for future day
    availability_update = {
        "availability": [tomorrow, future_day],
        "availability_time": {"from": "18:00", "to": "23:00"}
    }
    update_profile(target_token, availability_update)
    
    scheduled_at_cancel = f"{future_day}T18:00:00Z"
    resp = book_date(requester_a_token, target_user["id"], "Cancel Test Venue", "Test City",
                     scheduled_at_cancel, 400, activities=["Act 1", "Act 2", "Act 3"],
                     local_time="18:00")
    if resp.status_code != 200:
        log(f"❌ FAIL: Fresh booking failed: {resp.status_code} {resp.text}")
        return False
    
    booking_id_cancel = resp.json()["booking_id"]
    log(f"✅ Fresh booking created: {booking_id_cancel}")
    
    # Get initial balances
    log("\n5b) Getting initial coin balances...")
    inviter_coins_before, inviter_wd_before = get_user_balance(requester_a_token)
    target_coins_before, target_wd_before = get_user_balance(target_token)
    log(f"Inviter before: coins={inviter_coins_before}, withdrawable={inviter_wd_before}")
    log(f"Target before: coins={target_coins_before}, withdrawable={target_wd_before}")
    
    # Inviter cancels
    log("\n5c) Inviter (Requester A) cancelling the booking...")
    resp = cancel_date(requester_a_token, booking_id_cancel)
    if resp.status_code != 200:
        log(f"❌ FAIL: Cancellation failed: {resp.status_code} {resp.text}")
        return False
    
    cancel_data = resp.json()
    log(f"Cancel response: {json.dumps(cancel_data, indent=2)}")
    
    # Verify coin split: 50% refund, 25% compensation, 25% platform fee
    expected_refund = 200  # 50% of 400
    expected_compensation = 100  # 25% of 400
    expected_platform_fee = 100  # 25% of 400
    
    if cancel_data.get("refund") != expected_refund:
        log(f"❌ FAIL: Refund should be {expected_refund}, got {cancel_data.get('refund')}")
        return False
    if cancel_data.get("compensation") != expected_compensation:
        log(f"❌ FAIL: Compensation should be {expected_compensation}, got {cancel_data.get('compensation')}")
        return False
    if cancel_data.get("platform_fee") != expected_platform_fee:
        log(f"❌ FAIL: Platform fee should be {expected_platform_fee}, got {cancel_data.get('platform_fee')}")
        return False
    
    log("✅ PASS: Cancellation response shows correct split (50% refund, 25% compensation, 25% platform fee)")
    
    # Verify actual coin balances
    log("\n5d) Verifying actual coin balances after cancellation...")
    inviter_coins_after, inviter_wd_after = get_user_balance(requester_a_token)
    target_coins_after, target_wd_after = get_user_balance(target_token)
    log(f"Inviter after: coins={inviter_coins_after}, withdrawable={inviter_wd_after}")
    log(f"Target after: coins={target_coins_after}, withdrawable={target_wd_after}")
    
    # Inviter should have gained 200 coins back (50% refund)
    if inviter_coins_after != inviter_coins_before + expected_refund:
        log(f"❌ FAIL: Inviter coins should increase by {expected_refund}, got increase of {inviter_coins_after - inviter_coins_before}")
        return False
    
    # Target should have gained 100 in withdrawable (25% compensation)
    if target_wd_after != target_wd_before + expected_compensation:
        log(f"❌ FAIL: Target withdrawable should increase by {expected_compensation}, got increase of {target_wd_after - target_wd_before}")
        return False
    
    log("✅ PASS: Coin balances correctly updated (inviter +200 coins, target +100 withdrawable)")
    
    # TEST 6: CANCELLATION Scenario B (invitee/target cancels)
    log("\n" + "=" * 80)
    log("TEST 6: CANCELLATION Scenario B (invitee/target cancels)")
    log("=" * 80)
    
    # Create another fresh booking
    log("\n6a) Creating fresh booking for invitee cancellation test...")
    future_day_2 = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    # Update target availability
    availability_update = {
        "availability": [tomorrow, future_day, future_day_2],
        "availability_time": {"from": "18:00", "to": "23:00"}
    }
    update_profile(target_token, availability_update)
    
    scheduled_at_cancel_2 = f"{future_day_2}T18:00:00Z"
    resp = book_date(requester_a_token, target_user["id"], "Cancel Test 2", "Test City",
                     scheduled_at_cancel_2, 400, activities=["X", "Y", "Z"],
                     local_time="18:00")
    if resp.status_code != 200:
        log(f"❌ FAIL: Fresh booking 2 failed: {resp.status_code} {resp.text}")
        return False
    
    booking_id_cancel_2 = resp.json()["booking_id"]
    log(f"✅ Fresh booking 2 created: {booking_id_cancel_2}")
    
    # Get initial balances
    log("\n6b) Getting initial coin balances...")
    inviter_coins_before, inviter_wd_before = get_user_balance(requester_a_token)
    target_coins_before, target_wd_before = get_user_balance(target_token)
    log(f"Inviter before: coins={inviter_coins_before}, withdrawable={inviter_wd_before}")
    log(f"Target before: coins={target_coins_before}, withdrawable={target_wd_before}")
    
    # Target/invitee declines (which is same as cancelling)
    log("\n6c) Target declining the booking (100% refund to inviter)...")
    resp = respond_to_date(target_token, booking_id_cancel_2, accept=False)
    if resp.status_code != 200:
        log(f"❌ FAIL: Decline failed: {resp.status_code} {resp.text}")
        return False
    
    decline_data = resp.json()
    log(f"Decline response: {json.dumps(decline_data, indent=2)}")
    
    # Verify 100% refund to inviter
    if decline_data.get("refunded") != 400:
        log(f"❌ FAIL: Refunded should be 400 (100%), got {decline_data.get('refunded')}")
        return False
    
    log("✅ PASS: Decline response shows 100% refund to inviter")
    
    # Verify actual coin balances
    log("\n6d) Verifying actual coin balances after decline...")
    inviter_coins_after, inviter_wd_after = get_user_balance(requester_a_token)
    target_coins_after, target_wd_after = get_user_balance(target_token)
    log(f"Inviter after: coins={inviter_coins_after}, withdrawable={inviter_wd_after}")
    log(f"Target after: coins={target_coins_after}, withdrawable={target_wd_after}")
    
    # Inviter should have gained 400 coins back (100% refund)
    if inviter_coins_after != inviter_coins_before + 400:
        log(f"❌ FAIL: Inviter coins should increase by 400, got increase of {inviter_coins_after - inviter_coins_before}")
        return False
    
    log("✅ PASS: Coin balances correctly updated (inviter +400 coins, no penalty)")
    
    # All tests passed
    log("\n" + "=" * 80)
    log("✅ ALL TESTS PASSED!")
    log("=" * 80)
    return True

if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
