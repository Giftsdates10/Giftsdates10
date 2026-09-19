#!/usr/bin/env python3
"""
Backend API test for GiftsDates ACTIVE date-invitation flow using /api/invites endpoints
Tests: 3 mandatory CUSTOM activity options, recipient choice, safety_ack, invalid choices
"""
import requests
import json
from datetime import datetime
import sys

# Base URL from frontend/.env
BASE_URL = "https://login-vault-31.preview.emergentagent.com/api"

def log(msg):
    print(f"[TEST] {msg}")

def register_user(email, password, name, age=25, date_price=150):
    """Register a new user and return token + user data"""
    payload = {
        "email": email,
        "password": password,
        "name": name,
        "age": age,
        "gender": "female",
        "interested_in": "male",
        "city": "Los Angeles",
        "country": "USA"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    if resp.status_code != 200:
        log(f"❌ Registration failed for {email}: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json()
    
    # Set date_price for the user
    if date_price:
        headers = {"Authorization": f"Bearer {data['token']}"}
        update_resp = requests.patch(f"{BASE_URL}/auth/me", 
                                     json={"date_price": date_price}, 
                                     headers=headers)
        if update_resp.status_code != 200:
            log(f"⚠️  Warning: Could not set date_price: {update_resp.text}")
    
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

def create_invite(token, recipient_id, activity_option_1, activity_option_2, activity_option_3, 
                  coins, safety_ack=True):
    """Create a date invite"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "recipient_id": recipient_id,
        "activity_option_1": activity_option_1,
        "activity_option_2": activity_option_2,
        "activity_option_3": activity_option_3,
        "coins": coins,
        "safety_ack": safety_ack
    }
    resp = requests.post(f"{BASE_URL}/invites", json=payload, headers=headers)
    return resp

def get_invites(token):
    """Get all invites for user"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/invites", headers=headers)
    return resp

def get_invite(token, invite_id):
    """Get a specific invite"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/invites/{invite_id}", headers=headers)
    return resp

def choose_activity(token, invite_id, idea_id):
    """Recipient chooses an activity"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"idea_id": idea_id}
    resp = requests.post(f"{BASE_URL}/invites/{invite_id}/choose", json=payload, headers=headers)
    return resp

def run_tests():
    log("=" * 80)
    log("STARTING GIFTSDATES /api/invites ACTIVE DATE-INVITATION FLOW TESTS")
    log("=" * 80)
    
    # Register users
    log("\n📝 Registering test users...")
    timestamp = datetime.now().timestamp()
    
    inviter_token, inviter_user = register_user(
        f"inviter_{timestamp}@example.com",
        "SecurePass123!",
        "Emma Rodriguez",
        age=28,
        date_price=None  # Inviter doesn't need date_price
    )
    if not inviter_token:
        log("❌ Failed to register inviter")
        return False
    
    recipient_token, recipient_user = register_user(
        f"recipient_{timestamp}@example.com",
        "SecurePass456!",
        "Sophia Chen",
        age=26,
        date_price=150  # Recipient has date_price of 150
    )
    if not recipient_token:
        log("❌ Failed to register recipient")
        return False
    
    log(f"✅ Registered inviter: {inviter_user['name']} (ID: {inviter_user['id']})")
    log(f"✅ Registered recipient: {recipient_user['name']} (ID: {recipient_user['id']}, date_price: 150)")
    
    # Add coins to inviter
    log("\n💰 Adding coins to inviter...")
    add_coins_directly(inviter_user["id"], 500)
    
    # TEST 1: CREATE VALIDATION - Missing activity options
    log("\n" + "=" * 80)
    log("TEST 1: CREATE VALIDATION - Missing activity options")
    log("=" * 80)
    
    log("\n1) Creating invite with activity_option_3 BLANK (should be REJECTED)...")
    resp = create_invite(
        inviter_token,
        recipient_user["id"],
        activity_option_1="Coffee & a walk in the park",
        activity_option_2="Cocktails at a rooftop bar",
        activity_option_3="",  # BLANK
        coins=200,
        safety_ack=True
    )
    
    if resp.status_code == 400 and "ACTIVITIES_REQUIRED" in resp.text:
        log(f"✅ PASS: Invite rejected with 400 and detail 'ACTIVITIES_REQUIRED'")
        log(f"   Response: {resp.text}")
    else:
        log(f"❌ FAIL: Expected 400 with 'ACTIVITIES_REQUIRED', got {resp.status_code}: {resp.text}")
        return False
    
    # TEST 2: CREATE SUCCESS - All 3 activities provided
    log("\n" + "=" * 80)
    log("TEST 2: CREATE SUCCESS - All 3 custom activities provided")
    log("=" * 80)
    
    log("\n2) Creating invite with all 3 custom activities...")
    resp = create_invite(
        inviter_token,
        recipient_user["id"],
        activity_option_1="Coffee & a walk in the park",
        activity_option_2="Cocktails at a rooftop bar",
        activity_option_3="A round of mini-golf",
        coins=200,
        safety_ack=True
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Invite creation failed: {resp.status_code} {resp.text}")
        return False
    
    invite_data = resp.json()
    invite_id = invite_data.get("id")
    status = invite_data.get("status")
    
    if not invite_id:
        log(f"❌ FAIL: No invite ID returned")
        return False
    
    if status != "INVITATION_SENT":
        log(f"❌ FAIL: Expected status 'INVITATION_SENT', got '{status}'")
        return False
    
    log(f"✅ PASS: Invite created successfully")
    log(f"   Invite ID: {invite_id}")
    log(f"   Status: {status}")
    
    # TEST 3: OPTIONS STORED - Verify options are stored correctly
    log("\n" + "=" * 80)
    log("TEST 3: OPTIONS STORED - Verify 3 custom options are stored")
    log("=" * 80)
    
    log("\n3a) GET /api/invites as RECIPIENT...")
    resp = get_invites(recipient_token)
    if resp.status_code != 200:
        log(f"❌ FAIL: GET /api/invites failed: {resp.status_code} {resp.text}")
        return False
    
    invites_data = resp.json()
    incoming = invites_data.get("incoming", [])
    
    if not incoming:
        log(f"❌ FAIL: No incoming invites found for recipient")
        return False
    
    invite = None
    for inv in incoming:
        if inv.get("id") == invite_id:
            invite = inv
            break
    
    if not invite:
        log(f"❌ FAIL: Invite {invite_id} not found in recipient's incoming invites")
        return False
    
    log(f"✅ Found invite in recipient's incoming list")
    
    # Check options
    options = invite.get("options", [])
    if len(options) != 3:
        log(f"❌ FAIL: Expected 3 options, got {len(options)}")
        return False
    
    expected_names = [
        "Coffee & a walk in the park",
        "Cocktails at a rooftop bar",
        "A round of mini-golf"
    ]
    
    for i, opt in enumerate(options):
        expected_name = expected_names[i]
        actual_name = opt.get("name")
        idea_id = opt.get("idea_id")
        
        if actual_name != expected_name:
            log(f"❌ FAIL: Option {i+1} name mismatch. Expected '{expected_name}', got '{actual_name}'")
            return False
        
        if not idea_id or not idea_id.startswith("opt"):
            log(f"❌ FAIL: Option {i+1} idea_id should be like 'opt1/opt2/opt3', got '{idea_id}'")
            return False
        
        log(f"   ✓ Option {i+1}: name='{actual_name}', idea_id='{idea_id}'")
    
    # Check activity_option_1/2/3 fields
    activity_option_1 = invite.get("activity_option_1")
    activity_option_2 = invite.get("activity_option_2")
    activity_option_3 = invite.get("activity_option_3")
    
    if activity_option_1 != expected_names[0]:
        log(f"❌ FAIL: activity_option_1 mismatch. Expected '{expected_names[0]}', got '{activity_option_1}'")
        return False
    if activity_option_2 != expected_names[1]:
        log(f"❌ FAIL: activity_option_2 mismatch. Expected '{expected_names[1]}', got '{activity_option_2}'")
        return False
    if activity_option_3 != expected_names[2]:
        log(f"❌ FAIL: activity_option_3 mismatch. Expected '{expected_names[2]}', got '{activity_option_3}'")
        return False
    
    log(f"   ✓ activity_option_1: '{activity_option_1}'")
    log(f"   ✓ activity_option_2: '{activity_option_2}'")
    log(f"   ✓ activity_option_3: '{activity_option_3}'")
    
    # Check chosen_idea and selected_activity are null
    chosen_idea = invite.get("chosen_idea")
    selected_activity = invite.get("selected_activity")
    
    if chosen_idea is not None:
        log(f"❌ FAIL: chosen_idea should be null, got {chosen_idea}")
        return False
    if selected_activity is not None:
        log(f"❌ FAIL: selected_activity should be null, got {selected_activity}")
        return False
    
    log(f"   ✓ chosen_idea: null")
    log(f"   ✓ selected_activity: null")
    
    log(f"✅ PASS: All 3 options stored correctly with proper fields")
    
    log("\n3b) GET /api/invites as INVITER...")
    resp = get_invites(inviter_token)
    if resp.status_code != 200:
        log(f"❌ FAIL: GET /api/invites failed for inviter: {resp.status_code} {resp.text}")
        return False
    
    invites_data = resp.json()
    outgoing = invites_data.get("outgoing", [])
    
    invite_inviter = None
    for inv in outgoing:
        if inv.get("id") == invite_id:
            invite_inviter = inv
            break
    
    if not invite_inviter:
        log(f"❌ FAIL: Invite {invite_id} not found in inviter's outgoing invites")
        return False
    
    # Verify same options visible to inviter
    options_inviter = invite_inviter.get("options", [])
    if len(options_inviter) != 3:
        log(f"❌ FAIL: Inviter should see 3 options, got {len(options_inviter)}")
        return False
    
    log(f"✅ PASS: Inviter also sees the 3 custom options correctly")
    
    # TEST 4: RECIPIENT CHOOSES ONE
    log("\n" + "=" * 80)
    log("TEST 4: RECIPIENT CHOOSES ONE activity")
    log("=" * 80)
    
    log("\n4) Recipient choosing option 2 (Cocktails at a rooftop bar)...")
    resp = choose_activity(recipient_token, invite_id, "opt2")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Choose activity failed: {resp.status_code} {resp.text}")
        return False
    
    choice_data = resp.json()
    new_status = choice_data.get("status")
    
    if new_status != "DATE_ACTIVITY_SELECTED":
        log(f"❌ FAIL: Expected status 'DATE_ACTIVITY_SELECTED', got '{new_status}'")
        return False
    
    log(f"✅ PASS: Activity choice succeeded, status = {new_status}")
    
    # Verify chosen_idea and selected_activity are now set
    log("\n4b) Verifying chosen_idea and selected_activity are now set...")
    resp = get_invite(recipient_token, invite_id)
    if resp.status_code != 200:
        log(f"❌ FAIL: GET /api/invites/{invite_id} failed: {resp.status_code} {resp.text}")
        return False
    
    invite_updated = resp.json()
    chosen_idea = invite_updated.get("chosen_idea")
    selected_activity = invite_updated.get("selected_activity")
    
    if not chosen_idea:
        log(f"❌ FAIL: chosen_idea should be set, got {chosen_idea}")
        return False
    
    chosen_name = chosen_idea.get("name") if isinstance(chosen_idea, dict) else None
    if chosen_name != "Cocktails at a rooftop bar":
        log(f"❌ FAIL: chosen_idea.name should be 'Cocktails at a rooftop bar', got '{chosen_name}'")
        return False
    
    if selected_activity != "Cocktails at a rooftop bar":
        log(f"❌ FAIL: selected_activity should be 'Cocktails at a rooftop bar', got '{selected_activity}'")
        return False
    
    log(f"   ✓ chosen_idea.name: '{chosen_name}'")
    log(f"   ✓ selected_activity: '{selected_activity}'")
    log(f"✅ PASS: chosen_idea and selected_activity correctly set to option 2")
    
    # TEST 5: INVALID CHOICE
    log("\n" + "=" * 80)
    log("TEST 5: INVALID CHOICE - Wrong idea_id and wrong party")
    log("=" * 80)
    
    # Create a new invite for this test
    log("\n5a) Creating new invite for invalid choice tests...")
    add_coins_directly(inviter_user["id"], 300)  # Add more coins
    
    resp = create_invite(
        inviter_token,
        recipient_user["id"],
        activity_option_1="Dinner at Italian restaurant",
        activity_option_2="Movie night at cinema",
        activity_option_3="Bowling and arcade games",
        coins=200,
        safety_ack=True
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Second invite creation failed: {resp.status_code} {resp.text}")
        return False
    
    invite_id_2 = resp.json().get("id")
    log(f"✅ Second invite created: {invite_id_2}")
    
    log("\n5b) Recipient trying to choose with invalid idea_id='opt9'...")
    resp = choose_activity(recipient_token, invite_id_2, "opt9")
    
    if resp.status_code == 400 and "Invalid option" in resp.text:
        log(f"✅ PASS: Invalid idea_id rejected with 'Invalid option'")
        log(f"   Response: {resp.text}")
    else:
        log(f"❌ FAIL: Expected 400 with 'Invalid option', got {resp.status_code}: {resp.text}")
        return False
    
    log("\n5c) INVITER trying to choose (wrong party, should be 403)...")
    resp = choose_activity(inviter_token, invite_id_2, "opt1")
    
    if resp.status_code == 403:
        log(f"✅ PASS: Inviter choosing rejected with 403 Forbidden")
        log(f"   Response: {resp.text}")
    else:
        log(f"❌ FAIL: Expected 403 Forbidden, got {resp.status_code}: {resp.text}")
        return False
    
    # TEST 6: SAFETY ACK
    log("\n" + "=" * 80)
    log("TEST 6: SAFETY ACK - safety_ack=false should be rejected")
    log("=" * 80)
    
    log("\n6) Creating invite with safety_ack=false...")
    add_coins_directly(inviter_user["id"], 300)  # Add more coins
    
    resp = create_invite(
        inviter_token,
        recipient_user["id"],
        activity_option_1="Coffee date",
        activity_option_2="Lunch meeting",
        activity_option_3="Park walk",
        coins=200,
        safety_ack=False  # FALSE
    )
    
    if resp.status_code == 400 and "SAFETY_ACK_REQUIRED" in resp.text:
        log(f"✅ PASS: Invite with safety_ack=false rejected with 'SAFETY_ACK_REQUIRED'")
        log(f"   Response: {resp.text}")
    else:
        log(f"❌ FAIL: Expected 400 with 'SAFETY_ACK_REQUIRED', got {resp.status_code}: {resp.text}")
        return False
    
    # All tests passed
    log("\n" + "=" * 80)
    log("✅ ALL /api/invites TESTS PASSED!")
    log("=" * 80)
    log("\nSUMMARY:")
    log("  ✅ Test 1: CREATE VALIDATION - Missing activities rejected")
    log("  ✅ Test 2: CREATE SUCCESS - Invite created with 3 custom activities")
    log("  ✅ Test 3: OPTIONS STORED - All options stored correctly for both parties")
    log("  ✅ Test 4: RECIPIENT CHOOSES - Activity selection works, status updated")
    log("  ✅ Test 5: INVALID CHOICE - Invalid idea_id and wrong party rejected")
    log("  ✅ Test 6: SAFETY ACK - safety_ack=false rejected")
    
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
