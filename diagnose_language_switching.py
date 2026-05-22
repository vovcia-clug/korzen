#!/usr/bin/env python3
"""
Diagnostic script to identify why language switching is not working.

Potential issues to check:
1. Missing translation files (.po/.mo files)
2. Session not persisting (SECRET_KEY issue)
3. Babel not properly initialized
4. Template not using translated strings
5. Browser caching issues
"""

import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from flask import session

def check_translation_files():
    """Check if translation files exist and are compiled."""
    print("\n" + "="*60)
    print("1. CHECKING TRANSLATION FILES")
    print("="*60)
    
    translations_dir = "src/app/translations"
    
    for lang in ['pl', 'en']:
        po_file = os.path.join(translations_dir, lang, "LC_MESSAGES", "messages.po")
        mo_file = os.path.join(translations_dir, lang, "LC_MESSAGES", "messages.mo")
        
        print(f"\n{lang.upper()} Translation Files:")
        print(f"  .po file: {po_file}")
        print(f"    Exists: {os.path.exists(po_file)}")
        if os.path.exists(po_file):
            print(f"    Size: {os.path.getsize(po_file)} bytes")
        
        print(f"  .mo file: {mo_file}")
        print(f"    Exists: {os.path.exists(mo_file)}")
        if os.path.exists(mo_file):
            print(f"    Size: {os.path.getsize(mo_file)} bytes")
    
    # Check if any translation files exist
    has_translations = any(
        os.path.exists(os.path.join(translations_dir, lang, "LC_MESSAGES", "messages.mo"))
        for lang in ['pl', 'en']
    )
    
    if not has_translations:
        print("\n⚠️  WARNING: No compiled translation files (.mo) found!")
        print("   This means translations won't work even if language is switched.")
        return False
    
    return True

def check_secret_key():
    """Check if SECRET_KEY is properly configured."""
    print("\n" + "="*60)
    print("2. CHECKING SECRET_KEY CONFIGURATION")
    print("="*60)
    
    app = create_app()
    
    secret_key = app.config.get('SECRET_KEY')
    print(f"\nSECRET_KEY configured: {secret_key is not None}")
    
    if secret_key:
        print(f"SECRET_KEY length: {len(secret_key)} characters")
        print(f"SECRET_KEY type: {type(secret_key)}")
        
        # Check if it's the default insecure key
        if secret_key == 'dev':
            print("⚠️  WARNING: Using default 'dev' SECRET_KEY")
            print("   Sessions will work but are not secure for production")
        else:
            print("✓ SECRET_KEY is configured")
    else:
        print("❌ ERROR: SECRET_KEY is not configured!")
        print("   Sessions will NOT work without a SECRET_KEY")
        return False
    
    return True

def check_babel_initialization():
    """Check if Babel is properly initialized."""
    print("\n" + "="*60)
    print("3. CHECKING BABEL INITIALIZATION")
    print("="*60)
    
    app = create_app()
    
    # Check if babel extension is registered
    has_babel = 'babel' in app.extensions
    print(f"\nBabel extension registered: {has_babel}")
    
    if has_babel:
        babel = app.extensions['babel']
        print(f"Babel instance: {babel}")
        print(f"Babel locale selector configured: {babel.locale_selector is not None}")
    else:
        print("❌ ERROR: Babel extension not found!")
        return False
    
    # Check Babel configuration
    print(f"\nBabel Configuration:")
    print(f"  BABEL_DEFAULT_LOCALE: {app.config.get('BABEL_DEFAULT_LOCALE')}")
    print(f"  BABEL_SUPPORTED_LOCALES: {app.config.get('BABEL_SUPPORTED_LOCALES')}")
    print(f"  BABEL_TRANSLATION_DIRECTORIES: {app.config.get('BABEL_TRANSLATION_DIRECTORIES')}")
    
    return True

def test_language_switching():
    """Test the actual language switching mechanism."""
    print("\n" + "="*60)
    print("4. TESTING LANGUAGE SWITCHING MECHANISM")
    print("="*60)
    
    app = create_app()
    
    with app.test_client() as client:
        # Test 1: Check initial locale
        print("\nTest 1: Initial page load (no session)")
        response = client.get('/')
        print(f"  Status: {response.status_code}")
        
        with client.session_transaction() as sess:
            print(f"  Session language: {sess.get('language', 'Not set')}")
        
        # Test 2: Switch to English
        print("\nTest 2: Switch to English")
        response = client.get('/set-language/en', follow_redirects=False)
        print(f"  Status: {response.status_code}")
        print(f"  Redirect location: {response.location}")
        
        with client.session_transaction() as sess:
            lang = sess.get('language', 'Not set')
            print(f"  Session language after switch: {lang}")
            if lang != 'en':
                print(f"  ❌ ERROR: Expected 'en', got '{lang}'")
                return False
        
        # Test 3: Verify language persists
        print("\nTest 3: Load page after language switch")
        response = client.get('/')
        print(f"  Status: {response.status_code}")
        
        with client.session_transaction() as sess:
            lang = sess.get('language', 'Not set')
            print(f"  Session language persists: {lang}")
            if lang != 'en':
                print(f"  ❌ ERROR: Language did not persist! Expected 'en', got '{lang}'")
                return False
        
        # Test 4: Switch to Polish
        print("\nTest 4: Switch to Polish")
        response = client.get('/set-language/pl', follow_redirects=False)
        print(f"  Status: {response.status_code}")
        
        with client.session_transaction() as sess:
            lang = sess.get('language', 'Not set')
            print(f"  Session language after switch: {lang}")
            if lang != 'pl':
                print(f"  ❌ ERROR: Expected 'pl', got '{lang}'")
                return False
    
    print("\n✓ Language switching mechanism works correctly")
    return True

def check_template_usage():
    """Check if templates are using the translation function."""
    print("\n" + "="*60)
    print("5. CHECKING TEMPLATE TRANSLATION USAGE")
    print("="*60)
    
    # Check which templates exist and if they use base.html
    templates_dir = "src/app/templates"
    templates = [
        'index.html', 'persons.html', 'baptisms.html', 
        'marriages.html', 'deaths.html', 'duplicates.html', 
        'graph.html', 'mi.html'
    ]
    
    print("\nTemplate Analysis:")
    for template in templates:
        template_path = os.path.join(templates_dir, template)
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            extends_base = 'extends' in content and 'base.html' in content
            uses_translation = "{{ _(" in content or "{% trans %}" in content
            has_header_include = 'includes/header.html' in content
            
            print(f"\n  {template}:")
            print(f"    Extends base.html: {extends_base}")
            print(f"    Uses translation: {uses_translation}")
            print(f"    Includes header: {has_header_include}")
            
            if not extends_base and not has_header_include:
                print(f"    ⚠️  WARNING: Template doesn't extend base.html or include header")
                print(f"       Language switcher may not be visible!")
        else:
            print(f"\n  {template}: Not found")
    
    return True

def main():
    """Run all diagnostic checks."""
    print("="*60)
    print("LANGUAGE SWITCHING DIAGNOSTIC TOOL")
    print("="*60)
    
    results = {
        'translation_files': check_translation_files(),
        'secret_key': check_secret_key(),
        'babel_init': check_babel_initialization(),
        'switching_mechanism': test_language_switching(),
        'template_usage': check_template_usage()
    }
    
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    
    for check, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check.replace('_', ' ').title()}")
    
    print("\n" + "="*60)
    print("LIKELY ROOT CAUSES")
    print("="*60)
    
    if not results['translation_files']:
        print("\n🔴 PRIMARY ISSUE: Missing translation files")
        print("   Even though language switching works, you won't see any")
        print("   translated text because .mo files don't exist.")
        print("\n   SOLUTION:")
        print("   1. Extract strings: pybabel extract -F babel.cfg -k _l -o messages.pot .")
        print("   2. Initialize translations: pybabel init -i messages.pot -d src/app/translations -l pl")
        print("   3. Initialize translations: pybabel init -i messages.pot -d src/app/translations -l en")
        print("   4. Edit .po files with translations")
        print("   5. Compile: pybabel compile -d src/app/translations")
    
    if not results['secret_key']:
        print("\n🔴 PRIMARY ISSUE: SECRET_KEY not configured")
        print("   Sessions cannot work without a SECRET_KEY.")
        print("\n   SOLUTION: Set SECRET_KEY in .env file or config")
    
    if not results['switching_mechanism']:
        print("\n🔴 PRIMARY ISSUE: Language switching mechanism broken")
        print("   The /set-language route is not working correctly.")
    
    if results['translation_files'] and results['secret_key'] and results['switching_mechanism']:
        print("\n🟡 SECONDARY ISSUE: Templates not using translations")
        print("   Language switching works, but templates may not be")
        print("   using the translation functions {{ _('text') }}.")
        print("\n   SOLUTION: Refactor templates to use base.html and {{ _() }}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
