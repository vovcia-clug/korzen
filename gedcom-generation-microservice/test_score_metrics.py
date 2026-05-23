"""
Test script to verify Langfuse score metrics implementation.

This script tests that:
1. Score metrics can be added to traces
2. Individuals and families counts are properly tracked
3. Scores work with and without Langfuse enabled
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils import langfuse_tracer


def test_score_function():
    """Test the add_score function."""
    print("\n=== Testing Score Function ===")
    
    # Test basic score addition
    print("✓ Testing add_score() function...")
    langfuse_tracer.add_score(
        name="test_metric",
        value=42.0,
        comment="Test score"
    )
    print("  ✓ add_score() executed without errors")
    
    # Test with different value types
    print("✓ Testing with integer value...")
    langfuse_tracer.add_score(
        name="individuals_processed",
        value=10,
        comment="Test individuals count"
    )
    print("  ✓ Integer value accepted")
    
    print("✓ Testing with float value...")
    langfuse_tracer.add_score(
        name="families_processed",
        value=5.0,
        comment="Test families count"
    )
    print("  ✓ Float value accepted")
    
    # Test without comment
    print("✓ Testing without comment...")
    langfuse_tracer.add_score(
        name="test_no_comment",
        value=100
    )
    print("  ✓ Score without comment accepted")
    
    print("\n✅ All score function tests passed!")


def test_gedcom_counting():
    """Test GEDCOM record counting logic."""
    print("\n=== Testing GEDCOM Record Counting ===")
    
    # Sample GEDCOM content
    sample_gedcom = """0 HEAD
1 SOUR Test
1 GEDC
2 VERS 5.5.1
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
0 @I2@ INDI
1 NAME Jane /Smith/
1 SEX F
0 @I3@ INDI
1 NAME Baby /Doe/
1 SEX M
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
0 @F2@ FAM
1 HUSB @I1@
0 TRLR
"""
    
    # Import GedcomGenerator
    from services.gedcom_generator import GedcomGenerator
    from services.openrouter_client import OpenRouterClient
    
    # Create a minimal generator instance (we only need count_gedcom_records)
    # We'll pass None for openrouter_client since we're not making API calls
    class MockOpenRouterClient:
        pass
    
    generator = GedcomGenerator(
        openrouter_client=MockOpenRouterClient(),
        gedcom_version="5.5.1"
    )
    
    # Count records
    print("✓ Counting records in sample GEDCOM...")
    counts = generator.count_gedcom_records(sample_gedcom)
    
    print(f"  Individuals found: {counts['individuals']}")
    print(f"  Families found: {counts['families']}")
    
    # Verify counts
    assert counts['individuals'] == 3, f"Expected 3 individuals, got {counts['individuals']}"
    assert counts['families'] == 2, f"Expected 2 families, got {counts['families']}"
    
    print("  ✓ Counts are correct!")
    
    print("\n✅ GEDCOM counting tests passed!")


def test_score_with_observe_decorator():
    """Test that scores work within @observe decorated functions."""
    print("\n=== Testing Scores with @observe Decorator ===")
    
    @langfuse_tracer.observe(name="test-function")
    def test_function():
        """Test function with observe decorator."""
        # Simulate processing
        individuals = 15
        families = 7
        
        # Add scores
        langfuse_tracer.add_score(
            name="individuals_processed",
            value=individuals,
            comment="Test individuals in decorated function"
        )
        langfuse_tracer.add_score(
            name="families_processed",
            value=families,
            comment="Test families in decorated function"
        )
        
        return {"individuals": individuals, "families": families}
    
    print("✓ Calling @observe decorated function with scores...")
    result = test_function()
    print(f"  Result: {result}")
    print("  ✓ Function executed successfully with scores")
    
    print("\n✅ Decorator integration tests passed!")


def test_langfuse_availability():
    """Test Langfuse availability detection."""
    print("\n=== Testing Langfuse Availability ===")
    
    is_available = langfuse_tracer.is_available()
    print(f"✓ Langfuse available: {is_available}")
    
    if is_available:
        print("  ✓ Langfuse is properly installed and imported")
        print("  ℹ️  Scores will be sent to Langfuse")
    else:
        print("  ⚠️  Langfuse not available (graceful degradation)")
        print("  ℹ️  Scores will be no-ops (no errors)")
    
    print("\n✅ Availability check passed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Langfuse Score Metrics Test Suite")
    print("=" * 60)
    
    try:
        # Test 1: Langfuse availability
        test_langfuse_availability()
        
        # Test 2: Score function
        test_score_function()
        
        # Test 3: GEDCOM counting
        test_gedcom_counting()
        
        # Test 4: Scores with decorator
        test_score_with_observe_decorator()
        
        # Flush traces if Langfuse is available
        if langfuse_tracer.is_available():
            print("\n=== Flushing Langfuse Traces ===")
            langfuse_tracer.flush()
            print("✓ Traces flushed")
            print("\nℹ️  Check your Langfuse dashboard to see the scores!")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nScore metrics implementation is working correctly!")
        print("\nNext steps:")
        print("1. Run the microservice with real data")
        print("2. Check Langfuse dashboard for score metrics")
        print("3. Verify individuals_processed and families_processed appear")
        
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
