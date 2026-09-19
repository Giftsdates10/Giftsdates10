#!/usr/bin/env python3
"""
GiftsDates VIP Scheduling Module Test Suite
Tests the complete VIP scheduling flow including availability, booking, double-booking prevention, 
15-minute buffer, confirm/decline/cancel, and coin transactions.
"""
import requests
import json
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient
import os

# Read backend URL from frontend/.env
with open('/app/frontend/.env', 'r') as f:
    for line in f:
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip()
            break

# Read MongoDB URL from backend/.env
MONGO_URL = None
DB_NAME = None
with open('/app/backend/.env', 'r') as f:
    for line in f:
        if line.startswith('MONGO_URL='):
            MONGO_URL = line.split('=', 1)[1].strip().strip('"')
        elif line.startswith('DB_NAME='):
            DB_NAME = line.split('=', 1)[1].strip().strip('"')

API_BASE = f"{BASE_URL}/api"

print(f"Testing VIP Scheduling at: {API_BASE}")
print(f"MongoDB: {MONGO_URL}, DB: {DB_NAME}")
print("=" * 80)

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

# Global test data
user_a = None  # VIP user
user_b = None  # Regular user (requester)
booking_id = None
test_date = None

def setup_users():
    """Setup: Register 2 users and configure via MongoDB"""
    global user_a, user_b, test_date
    
    print("\n[SETUP] Registering two users and configuring via MongoDB")
    print("=" * 80)
    
    # Calculate a future date for testing (7 days from now)
    test_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    print(f"Test date for bookings: {test_date}")
    
    # Register User A (will be VIP)
    print("\n1. Registering User A (future VIP)...")
    email_a = f"vip_user_{uuid.uuid4().hex[:8]}@example.com"
    password_a = "VipPass123!"
    
    payload_a = {
        "email": email_a,
        "password": password_a,
        "name": "Alice VIP",
        "age": 28,
        "gender": "female",
        "interested_in": "male",
        "orientation": "straight",
        "city": "Los Angeles",
        "country": "USA",
        "bio": "VIP user for scheduling tests",
        "language": "en"
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/register", json=payload_a, timeout=10)
        if response.status_code == 200:
            data = response.json()
            user_a = {
                "email": email_a,
                "password": password_a,
                "token": data["token"],
                "user": data["user"],
                "id": data["user"]["id"]
            }
            print(f"✅ User A registered: {email_a} (ID: {user_a['id']})")
        else:
            print(f"❌ Failed to register User A: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception registering User A: {e}")
        return False
    
    # Register User B (regular user)
    print("\n2. Registering User B (regular user)...")
    email_b = f"regular_user_{uuid.uuid4().hex[:8]}@example.com"
    password_b = "RegularPass123!"
    
    payload_b = {
        "email": email_b,
        "password": password_b,
        "name": "Bob Regular",
        "age": 30,
        "gender": "male",
        "interested_in": "female",
        "orientation": "straight",
        "city": "New York",
        "country": "USA",
        "bio": "Regular user for scheduling tests",
        "language": "en"
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/register", json=payload_b, timeout=10)
        if response.status_code == 200:
            data = response.json()
            user_b = {
                "email": email_b,
                "password": password_b,
                "token": data["token"],
                "user": data["user"],
                "id": data["user"]["id"]
            }
            print(f"✅ User B registered: {email_b} (ID: {user_b['id']})")
        else:
            print(f"❌ Failed to register User B: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception registering User B: {e}")
        return False
    
    # Connect to MongoDB and update users
    print("\n3. Connecting to MongoDB to configure users...")
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Set User A as VIP with far-future vip_until and give coins
        print(f"   Setting User A as VIP (vip_until: 2030-01-01T00:00:00+00:00) and coins: 5000")
        result_a = db.users.update_one(
            {"id": user_a["id"]},
            {"$set": {
                "vip_until": "2030-01-01T00:00:00+00:00",
                "coins": 5000
            }}
        )
        print(f"   ✅ User A updated: matched={result_a.matched_count}, modified={result_a.modified_count}")
        
        # Give User B coins
        print(f"   Giving User B coins: 5000")
        result_b = db.users.update_one(
            {"id": user_b["id"]},
            {"$set": {"coins": 5000}}
        )
        print(f"   ✅ User B updated: matched={result_b.matched_count}, modified={result_b.modified_count}")
        
        # Verify updates
        user_a_db = db.users.find_one({"id": user_a["id"]}, {"_id": 0, "id": 1, "email": 1, "coins": 1, "vip_until": 1, "escrow": 1})
        user_b_db = db.users.find_one({"id": user_b["id"]}, {"_id": 0, "id": 1, "email": 1, "coins": 1, "escrow": 1})
        
        print(f"\n   User A in DB: {json.dumps(user_a_db, indent=4)}")
        print(f"   User B in DB: {json.dumps(user_b_db, indent=4)}")
        
        client.close()
        print("\n✅ Setup complete!")
        return True
        
    except Exception as e:
        print(f"❌ Exception configuring MongoDB: {e}")
        return False

def test_1_add_availability():
    """Test 1: VIP adds availability + non-VIP gets 403"""
    print("\n[TEST 1] Add Availability")
    print("=" * 80)
    
    # Test 1a: User A (VIP) adds availability
    print("\n1a. User A (VIP) adds availability...")
    payload = {
        "date": test_date,
        "start": "18:00",
        "end": "22:00",
        "slot_len": 60
    }
    
    headers_a = {"Authorization": f"Bearer {user_a['token']}"}
    
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/availability", json=payload, headers=headers_a, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS: VIP successfully added availability")
            print(f"   Block ID: {data.get('id')}")
            print(f"   Date: {data.get('date')}, Time: {data.get('start')}-{data.get('end')}")
            test_results["passed"].append("Test 1a: VIP add availability")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 1a: VIP add availability - status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 1a: VIP add availability - exception: {e}")
        return False
    
    # Test 1b: User B (non-VIP) tries to add availability - should get 403
    print("\n1b. User B (non-VIP) tries to add availability (should get 403)...")
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/availability", json=payload, headers=headers_b, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 403:
            data = response.json()
            if data.get("detail") == "VIP_REQUIRED":
                print(f"✅ PASS: Non-VIP correctly rejected with 403 VIP_REQUIRED")
                test_results["passed"].append("Test 1b: Non-VIP gets 403")
            else:
                print(f"❌ FAIL: Got 403 but wrong detail: {data.get('detail')}")
                test_results["failed"].append(f"Test 1b: Non-VIP 403 wrong detail - {data.get('detail')}")
                return False
        else:
            print(f"❌ FAIL: Expected 403, got {response.status_code}")
            test_results["failed"].append(f"Test 1b: Non-VIP should get 403, got {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 1b: Non-VIP 403 check - exception: {e}")
        return False
    
    return True

def test_2_get_slots():
    """Test 2: GET slots - should return 60-min slots all state=available"""
    print("\n[TEST 2] Get Available Slots")
    print("=" * 80)
    
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    
    try:
        response = requests.get(f"{API_BASE}/vip/schedule/{user_a['id']}/slots", headers=headers_b, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:1000]}")
        
        if response.status_code == 200:
            data = response.json()
            days = data.get("days", [])
            
            if not days:
                print(f"❌ FAIL: No days returned")
                test_results["failed"].append("Test 2: No slots returned")
                return False
            
            # Find our test date
            test_day = next((d for d in days if d["date"] == test_date), None)
            if not test_day:
                print(f"❌ FAIL: Test date {test_date} not found in slots")
                test_results["failed"].append(f"Test 2: Test date {test_date} not in slots")
                return False
            
            slots = test_day.get("slots", [])
            print(f"\n   Found {len(slots)} slots for {test_date}:")
            for slot in slots:
                print(f"      {slot['start']}-{slot['end']}: state={slot['state']}, slot_len={slot['slot_len']}")
            
            # Verify all slots are 60 minutes and available
            all_available = all(s["state"] == "available" for s in slots)
            all_60min = all(s["slot_len"] == 60 for s in slots)
            expected_count = 4  # 18:00-22:00 with 60-min slots = 4 slots
            
            if len(slots) == expected_count and all_available and all_60min:
                print(f"✅ PASS: All {expected_count} slots are 60-min and state=available")
                test_results["passed"].append("Test 2: Get slots")
                return True
            else:
                print(f"❌ FAIL: Slots validation failed")
                print(f"   Expected {expected_count} slots, got {len(slots)}")
                print(f"   All available: {all_available}")
                print(f"   All 60-min: {all_60min}")
                test_results["failed"].append(f"Test 2: Slots validation - count={len(slots)}, available={all_available}, 60min={all_60min}")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 2: Get slots - status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 2: Get slots - exception: {e}")
        return False

def test_3_book_slot():
    """Test 3: User B books a slot - verify coins and escrow"""
    global booking_id
    
    print("\n[TEST 3] Book Slot and Verify Coin Transactions")
    print("=" * 80)
    
    # Get initial coin balances
    print("\n3a. Getting initial coin balances...")
    headers_a = {"Authorization": f"Bearer {user_a['token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    
    try:
        resp_a = requests.get(f"{API_BASE}/auth/me", headers=headers_a, timeout=10)
        resp_b = requests.get(f"{API_BASE}/auth/me", headers=headers_b, timeout=10)
        
        user_a_before = resp_a.json()
        user_b_before = resp_b.json()
        
        coins_a_before = user_a_before.get("coins", 0)
        escrow_a_before = user_a_before.get("escrow", 0)
        coins_b_before = user_b_before.get("coins", 0)
        
        print(f"   User A before: coins={coins_a_before}, escrow={escrow_a_before}")
        print(f"   User B before: coins={coins_b_before}")
        
    except Exception as e:
        print(f"❌ FAIL: Exception getting initial balances - {e}")
        test_results["failed"].append(f"Test 3: Get initial balances - exception: {e}")
        return False
    
    # Book the slot
    print("\n3b. User B books 19:00-20:00 slot for 300 coins...")
    payload = {
        "date": test_date,
        "start": "19:00",
        "end": "20:00",
        "coins": 300,
        "activity": "Dinner"
    }
    
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/{user_a['id']}/book", json=payload, headers=headers_b, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            booking_id = data.get("booking_id")
            status = data.get("status")
            
            if status == "pending" and booking_id:
                print(f"✅ Booking created: ID={booking_id}, status={status}")
            else:
                print(f"❌ FAIL: Unexpected response - status={status}, booking_id={booking_id}")
                test_results["failed"].append(f"Test 3: Booking response - status={status}")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 3: Book slot - status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 3: Book slot - exception: {e}")
        return False
    
    # Verify coin transactions
    print("\n3c. Verifying coin transactions...")
    try:
        resp_a = requests.get(f"{API_BASE}/auth/me", headers=headers_a, timeout=10)
        resp_b = requests.get(f"{API_BASE}/auth/me", headers=headers_b, timeout=10)
        
        user_a_after = resp_a.json()
        user_b_after = resp_b.json()
        
        coins_a_after = user_a_after.get("coins", 0)
        escrow_a_after = user_a_after.get("escrow", 0)
        coins_b_after = user_b_after.get("coins", 0)
        
        print(f"   User A after: coins={coins_a_after}, escrow={escrow_a_after}")
        print(f"   User B after: coins={coins_b_after}")
        
        # Verify: B coins decreased by 300, A escrow increased by 300
        b_coins_diff = coins_b_before - coins_b_after
        a_escrow_diff = escrow_a_after - escrow_a_before
        
        print(f"\n   Changes:")
        print(f"      User B coins: {coins_b_before} -> {coins_b_after} (diff: -{b_coins_diff})")
        print(f"      User A escrow: {escrow_a_before} -> {escrow_a_after} (diff: +{a_escrow_diff})")
        
        if b_coins_diff == 300 and a_escrow_diff == 300:
            print(f"✅ PASS: Coin transactions correct - B paid 300, A escrow +300")
            test_results["passed"].append("Test 3: Book slot and coin transactions")
            return True
        else:
            print(f"❌ FAIL: Coin transactions incorrect")
            print(f"   Expected: B -300, A escrow +300")
            print(f"   Got: B -{b_coins_diff}, A escrow +{a_escrow_diff}")
            test_results["failed"].append(f"Test 3: Coin transactions - B -{b_coins_diff}, A escrow +{a_escrow_diff}")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Exception verifying coins - {e}")
        test_results["failed"].append(f"Test 3: Verify coins - exception: {e}")
        return False

def test_4_double_booking():
    """Test 4: Double-booking prevention and buffer zones"""
    print("\n[TEST 4] Double-Booking Prevention and 15-Min Buffer")
    print("=" * 80)
    
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    
    # Test 4a: Try to book overlapping slot (20:00-21:00) - should get 409
    print("\n4a. Trying to book overlapping slot 20:00-21:00 (should get 409 SLOT_TAKEN)...")
    payload_overlap = {
        "date": test_date,
        "start": "20:00",
        "end": "21:00",
        "coins": 300,
        "activity": "Coffee"
    }
    
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/{user_a['id']}/book", json=payload_overlap, headers=headers_b, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 409:
            data = response.json()
            if data.get("detail") == "SLOT_TAKEN":
                print(f"✅ PASS: Overlapping booking correctly rejected with 409 SLOT_TAKEN")
                test_results["passed"].append("Test 4a: Overlapping booking rejected")
            else:
                print(f"❌ FAIL: Got 409 but wrong detail: {data.get('detail')}")
                test_results["failed"].append(f"Test 4a: 409 wrong detail - {data.get('detail')}")
        else:
            print(f"❌ FAIL: Expected 409, got {response.status_code}")
            test_results["failed"].append(f"Test 4a: Overlapping booking should get 409, got {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 4a: Overlapping booking - exception: {e}")
    
    # Test 4b: Try to book within 15-min buffer before (18:00-19:00) - should get 409
    print("\n4b. Trying to book within 15-min buffer 18:00-19:00 (should get 409 SLOT_TAKEN)...")
    payload_buffer_before = {
        "date": test_date,
        "start": "18:00",
        "end": "19:00",
        "coins": 300,
        "activity": "Drinks"
    }
    
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/{user_a['id']}/book", json=payload_buffer_before, headers=headers_b, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 409:
            data = response.json()
            if data.get("detail") == "SLOT_TAKEN":
                print(f"✅ PASS: Buffer-zone booking correctly rejected with 409 SLOT_TAKEN")
                test_results["passed"].append("Test 4b: Buffer-zone booking rejected")
            else:
                print(f"❌ FAIL: Got 409 but wrong detail: {data.get('detail')}")
                test_results["failed"].append(f"Test 4b: 409 wrong detail - {data.get('detail')}")
        else:
            print(f"❌ FAIL: Expected 409, got {response.status_code}")
            test_results["failed"].append(f"Test 4b: Buffer booking should get 409, got {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 4b: Buffer booking - exception: {e}")
    
    # Test 4c: Verify slot states
    print("\n4c. Verifying slot states (pending, locked, available)...")
    try:
        response = requests.get(f"{API_BASE}/vip/schedule/{user_a['id']}/slots", headers=headers_b, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            days = data.get("days", [])
            test_day = next((d for d in days if d["date"] == test_date), None)
            
            if test_day:
                slots = test_day.get("slots", [])
                print(f"\n   Slot states after booking:")
                
                slot_states = {}
                for slot in slots:
                    slot_key = f"{slot['start']}-{slot['end']}"
                    slot_states[slot_key] = slot['state']
                    print(f"      {slot_key}: {slot['state']}")
                
                # Expected states:
                # 18:00-19:00: locked (buffer before 19:00-20:00)
                # 19:00-20:00: pending (booked)
                # 20:00-21:00: locked (buffer after 19:00-20:00)
                # 21:00-22:00: available (clear of buffer)
                
                expected = {
                    "18:00-19:00": "locked",
                    "19:00-20:00": "pending",
                    "20:00-21:00": "locked",
                    "21:00-22:00": "available"
                }
                
                all_correct = True
                for slot_key, expected_state in expected.items():
                    actual_state = slot_states.get(slot_key)
                    if actual_state != expected_state:
                        print(f"   ❌ {slot_key}: expected {expected_state}, got {actual_state}")
                        all_correct = False
                    else:
                        print(f"   ✅ {slot_key}: {actual_state} (correct)")
                
                if all_correct:
                    print(f"\n✅ PASS: All slot states correct (pending, locked, available)")
                    test_results["passed"].append("Test 4c: Slot states correct")
                else:
                    print(f"\n❌ FAIL: Some slot states incorrect")
                    test_results["failed"].append("Test 4c: Slot states incorrect")
            else:
                print(f"❌ FAIL: Test date not found in slots")
                test_results["failed"].append("Test 4c: Test date not in slots")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 4c: Get slots - status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 4c: Verify slot states - exception: {e}")

def test_5_pending_count():
    """Test 5: VIP gets pending bookings and count"""
    print("\n[TEST 5] VIP Pending Bookings and Count")
    print("=" * 80)
    
    headers_a = {"Authorization": f"Bearer {user_a['token']}"}
    
    # Test 5a: GET /vip/schedule/me
    print("\n5a. User A (VIP) gets schedule with pending bookings...")
    try:
        response = requests.get(f"{API_BASE}/vip/schedule/me", headers=headers_a, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:1000]}")
        
        if response.status_code == 200:
            data = response.json()
            pending = data.get("pending", [])
            pending_count = data.get("pending_count", 0)
            
            print(f"\n   Pending bookings: {len(pending)}")
            print(f"   Pending count: {pending_count}")
            
            if len(pending) > 0:
                print(f"\n   First pending booking:")
                print(f"      ID: {pending[0].get('id')}")
                print(f"      Date: {pending[0].get('date')}")
                print(f"      Time: {pending[0].get('start')}-{pending[0].get('end')}")
                print(f"      Coins: {pending[0].get('coins')}")
                print(f"      Activity: {pending[0].get('activity')}")
                print(f"      Status: {pending[0].get('status')}")
            
            if pending_count == 1 and len(pending) == 1:
                print(f"\n✅ PASS: Pending count = 1, pending list has 1 booking")
                test_results["passed"].append("Test 5a: VIP schedule/me")
            else:
                print(f"\n❌ FAIL: Expected pending_count=1 and 1 booking, got count={pending_count}, list={len(pending)}")
                test_results["failed"].append(f"Test 5a: Pending count/list mismatch - count={pending_count}, list={len(pending)}")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 5a: VIP schedule/me - status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 5a: VIP schedule/me - exception: {e}")
    
    # Test 5b: GET /vip/schedule/pending-count
    print("\n5b. User A (VIP) gets pending count...")
    try:
        response = requests.get(f"{API_BASE}/vip/schedule/pending-count", headers=headers_a, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            count = data.get("count", 0)
            
            if count == 1:
                print(f"✅ PASS: Pending count endpoint returns 1")
                test_results["passed"].append("Test 5b: Pending count endpoint")
            else:
                print(f"❌ FAIL: Expected count=1, got {count}")
                test_results["failed"].append(f"Test 5b: Pending count - expected 1, got {count}")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 5b: Pending count - status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 5b: Pending count - exception: {e}")

def test_6_confirm_booking():
    """Test 6: VIP confirms the booking"""
    print("\n[TEST 6] VIP Confirms Booking")
    print("=" * 80)
    
    headers_a = {"Authorization": f"Bearer {user_a['token']}"}
    
    print(f"\nUser A (VIP) confirms booking {booking_id}...")
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/bookings/{booking_id}/confirm", headers=headers_a, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status == "confirmed":
                print(f"✅ PASS: Booking confirmed successfully")
                test_results["passed"].append("Test 6: Confirm booking")
                return True
            else:
                print(f"❌ FAIL: Expected status=confirmed, got {status}")
                test_results["failed"].append(f"Test 6: Confirm - status={status}")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 6: Confirm - status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 6: Confirm - exception: {e}")
        return False

def test_7_decline_cancel():
    """Test 7: Test decline/cancel with refund"""
    print("\n[TEST 7] Decline/Cancel with Refund")
    print("=" * 80)
    
    # First, create a new booking to test decline
    print("\n7a. Creating a new booking to test decline...")
    headers_a = {"Authorization": f"Bearer {user_a['token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    
    # Book the 21:00-22:00 slot (which should be available)
    payload = {
        "date": test_date,
        "start": "21:00",
        "end": "22:00",
        "coins": 400,
        "activity": "Late dinner"
    }
    
    try:
        # Get initial balances
        resp_a = requests.get(f"{API_BASE}/auth/me", headers=headers_a, timeout=10)
        resp_b = requests.get(f"{API_BASE}/auth/me", headers=headers_b, timeout=10)
        
        coins_b_before = resp_b.json().get("coins", 0)
        escrow_a_before = resp_a.json().get("escrow", 0)
        
        print(f"   Before booking: B coins={coins_b_before}, A escrow={escrow_a_before}")
        
        # Create booking
        response = requests.post(f"{API_BASE}/vip/schedule/{user_a['id']}/book", json=payload, headers=headers_b, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            decline_booking_id = data.get("booking_id")
            print(f"   ✅ New booking created: {decline_booking_id}")
            
            # Verify coins were deducted
            resp_b = requests.get(f"{API_BASE}/auth/me", headers=headers_b, timeout=10)
            resp_a = requests.get(f"{API_BASE}/auth/me", headers=headers_a, timeout=10)
            
            coins_b_after_book = resp_b.json().get("coins", 0)
            escrow_a_after_book = resp_a.json().get("escrow", 0)
            
            print(f"   After booking: B coins={coins_b_after_book}, A escrow={escrow_a_after_book}")
            print(f"   Changes: B -{coins_b_before - coins_b_after_book}, A escrow +{escrow_a_after_book - escrow_a_before}")
            
        else:
            print(f"❌ FAIL: Could not create test booking - {response.status_code}")
            test_results["failed"].append(f"Test 7: Create test booking - status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Exception creating test booking - {e}")
        test_results["failed"].append(f"Test 7: Create test booking - exception: {e}")
        return False
    
    # Now decline the booking
    print("\n7b. User A (VIP) declines the booking...")
    try:
        response = requests.post(f"{API_BASE}/vip/schedule/bookings/{decline_booking_id}/decline", headers=headers_a, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            refunded = data.get("refunded", 0)
            
            print(f"   Status: {status}, Refunded: {refunded}")
            
            # Verify refund
            resp_b = requests.get(f"{API_BASE}/auth/me", headers=headers_b, timeout=10)
            resp_a = requests.get(f"{API_BASE}/auth/me", headers=headers_a, timeout=10)
            
            coins_b_after_decline = resp_b.json().get("coins", 0)
            escrow_a_after_decline = resp_a.json().get("escrow", 0)
            
            print(f"   After decline: B coins={coins_b_after_decline}, A escrow={escrow_a_after_decline}")
            
            # Verify: B coins should be back to before booking, A escrow should be back to before booking
            b_refund = coins_b_after_decline - coins_b_after_book
            a_escrow_release = escrow_a_after_book - escrow_a_after_decline
            
            print(f"   Refund verification: B +{b_refund}, A escrow -{a_escrow_release}")
            
            if status == "declined" and b_refund == 400 and a_escrow_release == 400:
                print(f"✅ PASS: Decline successful with correct refund")
                test_results["passed"].append("Test 7: Decline with refund")
            else:
                print(f"❌ FAIL: Decline refund incorrect")
                print(f"   Expected: status=declined, B +400, A escrow -400")
                print(f"   Got: status={status}, B +{b_refund}, A escrow -{a_escrow_release}")
                test_results["failed"].append(f"Test 7: Decline refund - status={status}, B +{b_refund}, A escrow -{a_escrow_release}")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 7: Decline - status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 7: Decline - exception: {e}")
    
    # Verify slot is available again
    print("\n7c. Verifying slot is available again after decline...")
    try:
        response = requests.get(f"{API_BASE}/vip/schedule/{user_a['id']}/slots", headers=headers_b, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            days = data.get("days", [])
            test_day = next((d for d in days if d["date"] == test_date), None)
            
            if test_day:
                slots = test_day.get("slots", [])
                slot_21_22 = next((s for s in slots if s["start"] == "21:00" and s["end"] == "22:00"), None)
                
                if slot_21_22 and slot_21_22["state"] == "available":
                    print(f"✅ PASS: Slot 21:00-22:00 is available again after decline")
                    test_results["passed"].append("Test 7c: Slot freed after decline")
                else:
                    print(f"❌ FAIL: Slot 21:00-22:00 state is {slot_21_22['state'] if slot_21_22 else 'not found'}")
                    test_results["failed"].append(f"Test 7c: Slot not freed - state={slot_21_22['state'] if slot_21_22 else 'not found'}")
            else:
                print(f"❌ FAIL: Test date not found")
                test_results["failed"].append("Test 7c: Test date not found")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 7c: Get slots - status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 7c: Verify slot freed - exception: {e}")

def test_8_my_requests():
    """Test 8: User B gets their booking requests with vip_card"""
    print("\n[TEST 8] Requester Gets Booking List")
    print("=" * 80)
    
    headers_b = {"Authorization": f"Bearer {user_b['token']}"}
    
    print("\nUser B gets their booking requests...")
    try:
        response = requests.get(f"{API_BASE}/vip/schedule/bookings/mine", headers=headers_b, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:1000]}")
        
        if response.status_code == 200:
            data = response.json()
            requests_list = data.get("requests", [])
            
            print(f"\n   Found {len(requests_list)} booking requests")
            
            if len(requests_list) > 0:
                # Check if vip_card is present
                has_vip_card = all("vip_card" in req for req in requests_list)
                
                print(f"\n   Sample booking:")
                sample = requests_list[0]
                print(f"      ID: {sample.get('id')}")
                print(f"      VIP ID: {sample.get('vip_id')}")
                print(f"      Date: {sample.get('date')}")
                print(f"      Time: {sample.get('start')}-{sample.get('end')}")
                print(f"      Status: {sample.get('status')}")
                print(f"      VIP Card: {sample.get('vip_card')}")
                
                if has_vip_card:
                    print(f"\n✅ PASS: Booking list includes vip_card for all requests")
                    test_results["passed"].append("Test 8: My requests with vip_card")
                else:
                    print(f"\n❌ FAIL: Some requests missing vip_card")
                    test_results["failed"].append("Test 8: Missing vip_card in some requests")
            else:
                print(f"\n❌ FAIL: No booking requests found (expected at least 1)")
                test_results["failed"].append("Test 8: No booking requests found")
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            test_results["failed"].append(f"Test 8: My requests - status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL: Exception - {e}")
        test_results["failed"].append(f"Test 8: My requests - exception: {e}")

def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("VIP SCHEDULING TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(test_results["passed"]) + len(test_results["failed"])
    
    print(f"\n✅ PASSED ({len(test_results['passed'])}/{total_tests} tests):")
    for test in test_results["passed"]:
        print(f"   - {test}")
    
    if test_results["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(test_results['warnings'])} items):")
        for warning in test_results["warnings"]:
            print(f"   - {warning}")
    
    if test_results["failed"]:
        print(f"\n❌ FAILED ({len(test_results['failed'])} tests):")
        for test in test_results["failed"]:
            print(f"   - {test}")
    else:
        print(f"\n🎉 All VIP Scheduling tests passed!")
    
    print("\n" + "=" * 80)
    
    # Return exit code
    return 0 if len(test_results["failed"]) == 0 else 1

def main():
    """Run all VIP Scheduling tests"""
    print(f"Starting VIP Scheduling Tests at {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Setup users
    if not setup_users():
        print("\n❌ Setup failed - cannot continue with tests")
        return 1
    
    # Run tests in sequence
    test_1_add_availability()
    test_2_get_slots()
    test_3_book_slot()
    test_4_double_booking()
    test_5_pending_count()
    test_6_confirm_booking()
    test_7_decline_cancel()
    test_8_my_requests()
    
    # Print summary
    return print_summary()

if __name__ == "__main__":
    exit(main())
