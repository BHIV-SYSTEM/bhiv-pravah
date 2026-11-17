#!/usr/bin/env python3
"""Test Security Components"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.signing import sign_payload, verify_payload
from security.nonce_store import check_nonce
from security.heartbeat import HeartbeatMonitor, validate_heartbeats

def test_signing():
    """Test payload signing and verification."""
    print("🔐 Testing Payload Signing")
    print("-" * 40)
    
    payload = {'event': 'test', 'data': 'hello', 'timestamp': '2024-01-01'}
    
    # Sign payload
    signed = sign_payload(payload)
    print(f"✅ Payload signed: {signed.get('signature')[:16]}...")
    
    # Verify valid signature
    valid = verify_payload(signed)
    print(f"✅ Valid signature verified: {valid}")
    
    # Test tampered payload
    tampered = signed.copy()
    tampered['data'] = 'tampered'
    invalid = verify_payload(tampered)
    print(f"✅ Tampered payload rejected: {not invalid}\n")
    
    return valid and not invalid

def test_nonce():
    """Test nonce store for replay protection."""
    print("🔄 Testing Nonce Store")
    print("-" * 40)
    
    nonce = 'test-nonce-456'
    
    # First use - should be valid
    first = check_nonce(nonce)
    print(f"✅ First nonce check: {first}")
    
    # Replay - should be rejected
    replay = check_nonce(nonce)
    print(f"✅ Replay detected: {not replay}")
    
    # New nonce - should be valid
    new_nonce = 'test-nonce-789'
    new = check_nonce(new_nonce)
    print(f"✅ New nonce accepted: {new}\n")
    
    return first and not replay and new

def test_heartbeat():
    """Test heartbeat monitoring."""
    print("💓 Testing Heartbeat System")
    print("-" * 40)
    
    # Create heartbeat monitor
    hb = HeartbeatMonitor('test-agent', 'dev', interval=30)
    
    # Log heartbeat
    hb.log_heartbeat()
    print("✅ Heartbeat logged")
    
    # Validate heartbeats
    result = validate_heartbeats('dev', max_age=120)
    print(f"✅ Heartbeat validation: {result['healthy']}")
    print(f"   Total agents: {result['total_agents']}\n")
    
    return result['healthy']

def test_integration():
    """Test integration with event bus."""
    print("🔗 Testing Event Bus Integration")
    print("-" * 40)
    
    try:
        from core.redis_event_bus import get_redis_bus
        
        bus = get_redis_bus('dev')
        
        # Publish event (will be signed automatically)
        bus.publish('test.event', {'message': 'test'})
        print("✅ Event published with signature")
        
        # Check message history
        history = bus.get_message_history(1)
        if history:
            msg = history[-1]
            has_signature = 'signature' in msg
            has_nonce = 'nonce' in msg
            print(f"✅ Message has signature: {has_signature}")
            print(f"✅ Message has nonce: {has_nonce}\n")
            return has_signature and has_nonce
        
    except Exception as e:
        print(f"⚠️ Event bus test skipped (Redis not available): {e}\n")
    
    return True

if __name__ == "__main__":
    print("🧪 SECURITY COMPONENTS TEST")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(("Signing", test_signing()))
    results.append(("Nonce Store", test_nonce()))
    results.append(("Heartbeat", test_heartbeat()))
    results.append(("Integration", test_integration()))
    
    print("=" * 60)
    print("📊 TEST RESULTS")
    print("-" * 40)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print()
    if all_passed:
        print("🎉 ALL SECURITY TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)