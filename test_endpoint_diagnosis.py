"""
Diagnostic script to verify Flask endpoint names.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app

def diagnose_endpoints():
    """List all registered Flask endpoints."""
    app = create_app()
    
    print("=" * 60)
    print("REGISTERED FLASK ENDPOINTS")
    print("=" * 60)
    
    with app.app_context():
        # Get all URL rules
        for rule in app.url_map.iter_rules():
            if 'graph' in rule.endpoint.lower() or 'graph' in rule.rule.lower():
                print(f"\n🔍 GRAPH-RELATED ENDPOINT FOUND:")
                print(f"   Endpoint: {rule.endpoint}")
                print(f"   URL Path: {rule.rule}")
                print(f"   Methods: {', '.join(rule.methods - {'HEAD', 'OPTIONS'})}")
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    print("\nExpected endpoint: 'main.graph'")
    print("If you see 'main.graph_visualizer' instead, that's the issue!")

if __name__ == "__main__":
    diagnose_endpoints()
