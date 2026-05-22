#!/usr/bin/env python3
"""Test script to verify the locale fix works in both contexts."""

import sys
sys.path.insert(0, 'src')

from app import create_app

def test_locale_outside_request_context():
    """Test that get_locale works during app initialization."""
    print("Testing locale outside request context...")
    try:
        app = create_app()
        print("✓ App created successfully - no RuntimeError!")
        return True
    except RuntimeError as e:
        print(f"✗ RuntimeError occurred: {e}")
        return False

def test_locale_inside_request_context():
    """Test that get_locale works during an actual request."""
    print("\nTesting locale inside request context...")
    app = create_app()
    
    # Ensure secret key is set for session testing
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'test-secret-key-for-testing'
    
    with app.test_client() as client:
        with app.app_context():
            from app import get_locale
            
            # Test 1: Default locale (no session)
            with app.test_request_context():
                locale = get_locale()
                print(f"  Default locale (no session): {locale}")
                assert locale in ['pl', 'en'], f"Expected 'pl' or 'en', got {locale}"
            
            # Test 2: With session language
            with app.test_request_context():
                from flask import session
                session['language'] = 'en'
                locale = get_locale()
                print(f"  Locale with session['language']='en': {locale}")
                assert locale == 'en', f"Expected 'en', got {locale}"
            
            print("✓ All request context tests passed!")
            return True

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Flask-Babel locale fix")
    print("=" * 60)
    
    test1 = test_locale_outside_request_context()
    test2 = test_locale_inside_request_context()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("✓ ALL TESTS PASSED - Fix is working correctly!")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
