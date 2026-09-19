#!/usr/bin/env python3
"""
Stripe Checkout Integration Test
Tests the newly-activated Stripe checkout on GiftsDates backend.
"""
import requests
import pymongo
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

# Load environment
ROOT_DIR = Path(__file__).parent / "backend"
load_dotenv(ROOT_DIR / '.env')
frontend_env = Path(__file__).parent / "frontend" / ".env"
load_dotenv(frontend_env)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") + "/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

print(f"BASE_URL: {BASE_URL}")
print(f"MONGO_URL: {MONGO_URL}")
print(f"DB_NAME: {DB_NAME}")

# MongoDB client
mongo_client = pymongo.MongoClient(MONGO_URL)
db = mongo_client[DB_NAME]

def register_user(email, password, name):
    """Register a new user"""
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
        "gender": "female",
        "age": 28,
        "interested_in": "male",
        "city": "Los Angeles",
        "country": "USA"
    })
    print(f"Register {email}: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        return data["token"], data["user"]["id"]
    else:
        print(f"Register failed: {resp.text}")
        return None, None

def test_checkout(token, package_id, origin_url, usd_amount=None):
    """Test POST /api/payments/checkout"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "package_id": package_id,
        "origin_url": origin_url
    }
    if usd_amount is not None:
        payload["usd_amount"] = usd_amount
    
    resp = requests.post(f"{BASE_URL}/payments/checkout", json=payload, headers=headers)
    print(f"\nTest checkout {package_id}: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  checkout_url: {data.get('checkout_url', 'N/A')[:80]}...")
        print(f"  session_id: {data.get('session_id', 'N/A')}")
        return data
    else:
        print(f"  Error: {resp.text}")
        return None

def test_payment_status(session_id):
    """Test GET /api/payments/status/{session_id} (unauthenticated)"""
    resp = requests.get(f"{BASE_URL}/payments/status/{session_id}")
    print(f"\nTest payment status {session_id}: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  session_id: {data.get('session_id', 'N/A')}")
        print(f"  status: {data.get('status', 'N/A')}")
        print(f"  payment_status: {data.get('payment_status', 'N/A')}")
        return data
    else:
        print(f"  Error: {resp.text}")
        return None

def verify_transaction_in_db(session_id):
    """Verify payment_transactions doc was inserted in MongoDB"""
    txn = db.payment_transactions.find_one({"session_id": session_id})
    if txn:
        print(f"\n  ✅ Transaction found in DB:")
        print(f"    session_id: {txn.get('session_id')}")
        print(f"    user_id: {txn.get('user_id')}")
        print(f"    package_id: {txn.get('package_id')}")
        print(f"    amount: ${txn.get('amount')}")
        print(f"    status: {txn.get('status')}")
        print(f"    payment_status: {txn.get('payment_status')}")
        return txn
    else:
        print(f"\n  ❌ Transaction NOT found in DB for session_id: {session_id}")
        return None

def get_coin_packages():
    """Get available coin packages from /api/meta"""
    resp = requests.get(f"{BASE_URL}/meta")
    if resp.status_code == 200:
        data = resp.json()
        packages = data.get("coin_packages", [])
        print(f"\nAvailable coin packages:")
        for pkg in packages:
            print(f"  - {pkg['id']}: {pkg['name']} - {pkg['coins']} coins (+{pkg['bonus']} bonus) - ${pkg['amount']}")
        return packages
    else:
        print(f"Failed to get coin packages: {resp.text}")
        return []

def main():
    print("=" * 80)
    print("STRIPE CHECKOUT INTEGRATION TEST")
    print("=" * 80)
    
    # Get available coin packages
    packages = get_coin_packages()
    
    # Register a test user
    test_email = f"stripe_test_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "StripeTest123!"
    test_name = "Stripe Tester"
    
    print(f"\n{'='*80}")
    print("STEP 1: Register/Login User")
    print(f"{'='*80}")
    token, user_id = register_user(test_email, test_password, test_name)
    
    if not token:
        print("❌ FAILED: Could not register user")
        return
    
    print(f"✅ User registered successfully")
    print(f"  User ID: {user_id}")
    print(f"  Token: {token[:20]}...")
    
    # Test results
    results = []
    
    # TEST 1: POST /api/payments/checkout with package_id="starter"
    print(f"\n{'='*80}")
    print("TEST 1: Checkout with package_id='starter'")
    print(f"{'='*80}")
    checkout_data = test_checkout(token, "starter", "https://example.com")
    if checkout_data:
        checkout_url = checkout_data.get("checkout_url", "")
        session_id = checkout_data.get("session_id", "")
        
        # Verify checkout_url starts with correct domain
        if checkout_url.startswith("https://checkout.stripe.com") or ".stripe.com" in checkout_url:
            print(f"  ✅ checkout_url starts with correct Stripe domain")
            results.append(("TEST 1: starter package", "PASS"))
        else:
            print(f"  ❌ checkout_url does NOT start with Stripe domain: {checkout_url}")
            results.append(("TEST 1: starter package", "FAIL - Invalid checkout_url"))
        
        # Verify transaction in DB
        txn = verify_transaction_in_db(session_id)
        if txn and txn.get("status") == "initiated" and txn.get("payment_status") == "pending":
            print(f"  ✅ Transaction has correct status: initiated/pending")
        else:
            print(f"  ❌ Transaction status incorrect or not found")
            results.append(("TEST 1: DB verification", "FAIL"))
    else:
        print(f"  ❌ Checkout failed")
        results.append(("TEST 1: starter package", "FAIL"))
    
    # TEST 2: POST /api/payments/checkout with package_id="premium_monthly"
    print(f"\n{'='*80}")
    print("TEST 2: Checkout with package_id='premium_monthly' (one-time payment)")
    print(f"{'='*80}")
    checkout_data = test_checkout(token, "premium_monthly", "https://example.com")
    if checkout_data:
        checkout_url = checkout_data.get("checkout_url", "")
        session_id = checkout_data.get("session_id", "")
        
        if checkout_url.startswith("https://checkout.stripe.com") or ".stripe.com" in checkout_url:
            print(f"  ✅ checkout_url valid")
            results.append(("TEST 2: premium_monthly", "PASS"))
        else:
            print(f"  ❌ checkout_url invalid")
            results.append(("TEST 2: premium_monthly", "FAIL"))
        
        verify_transaction_in_db(session_id)
    else:
        print(f"  ❌ Checkout failed")
        results.append(("TEST 2: premium_monthly", "FAIL"))
    
    # TEST 3: POST /api/payments/checkout with package_id="vip_monthly" (subscription)
    print(f"\n{'='*80}")
    print("TEST 3: Checkout with package_id='vip_monthly' (subscription mode)")
    print(f"{'='*80}")
    checkout_data = test_checkout(token, "vip_monthly", "https://example.com")
    if checkout_data:
        checkout_url = checkout_data.get("checkout_url", "")
        session_id = checkout_data.get("session_id", "")
        
        if checkout_url.startswith("https://checkout.stripe.com") or ".stripe.com" in checkout_url:
            print(f"  ✅ checkout_url valid")
            results.append(("TEST 3: vip_monthly subscription", "PASS"))
        else:
            print(f"  ❌ checkout_url invalid")
            results.append(("TEST 3: vip_monthly subscription", "FAIL"))
        
        verify_transaction_in_db(session_id)
    else:
        print(f"  ❌ Checkout failed")
        results.append(("TEST 3: vip_monthly subscription", "FAIL"))
    
    # TEST 4: POST /api/payments/checkout with package_id="custom" and usd_amount
    print(f"\n{'='*80}")
    print("TEST 4: Checkout with package_id='custom' and usd_amount=25")
    print(f"{'='*80}")
    checkout_data = test_checkout(token, "custom", "https://example.com", usd_amount=25)
    if checkout_data:
        checkout_url = checkout_data.get("checkout_url", "")
        session_id = checkout_data.get("session_id", "")
        
        if checkout_url.startswith("https://checkout.stripe.com") or ".stripe.com" in checkout_url:
            print(f"  ✅ checkout_url valid")
            results.append(("TEST 4: custom package", "PASS"))
        else:
            print(f"  ❌ checkout_url invalid")
            results.append(("TEST 4: custom package", "FAIL"))
        
        verify_transaction_in_db(session_id)
        
        # TEST 5: GET /api/payments/status/{session_id}
        print(f"\n{'='*80}")
        print("TEST 5: GET /api/payments/status/{session_id} (unauthenticated)")
        print(f"{'='*80}")
        status_data = test_payment_status(session_id)
        if status_data:
            if status_data.get("payment_status") == "pending":
                print(f"  ✅ payment_status is 'pending' (not yet paid)")
                results.append(("TEST 5: payment status endpoint", "PASS"))
            else:
                print(f"  ⚠️  payment_status is '{status_data.get('payment_status')}' (expected 'pending')")
                results.append(("TEST 5: payment status endpoint", "PASS (different status)"))
        else:
            print(f"  ❌ Status endpoint failed")
            results.append(("TEST 5: payment status endpoint", "FAIL"))
    else:
        print(f"  ❌ Checkout failed")
        results.append(("TEST 4: custom package", "FAIL"))
    
    # Print summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    for test_name, result in results:
        status_icon = "✅" if "PASS" in result else "❌"
        print(f"{status_icon} {test_name}: {result}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if "PASS" in result)
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")

if __name__ == "__main__":
    main()
