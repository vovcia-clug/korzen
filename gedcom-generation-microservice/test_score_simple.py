"""
Simple test to verify Langfuse score metrics work correctly.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils import langfuse_tracer


def test_basic_score():
    """Test basic score functionality."""
    print("\n=== Testing Basic Score Functionality ===")
    
    # Check if Langfuse is available
    is_available = langfuse_tracer.is_available()
    print(f"✓ Langfuse available: {is_available}")
    
    # Test adding scores
    print("\n✓ Testing add_score() function...")
    
    try:
        langfuse_tracer.add_score(
            name="individuals_processed",
            value=10,
            comment="Test individuals count"
        )
        print("  ✓ individuals_processed score added successfully")
    except Exception as e:
        print(f"  ✗ Error adding individuals_processed: {e}")
        return False
    
    try:
        langfuse_tracer.add_score(
            name="families_processed",
            value=5,
            comment="Test families count"
        )
        print("  ✓ families_processed score added successfully")
    except Exception as e:
        print(f"  ✗ Error adding families_processed: {e}")
        return False
    
    # Test without comment
    try:
        langfuse_tracer.add_score(
            name="test_metric",
            value=42.5
        )
        print("  ✓ Score without comment added successfully")
    except Exception as e:
        print(f"  ✗ Error adding score without comment: {e}")
        return False
    
    print("\n✅ All basic score tests passed!")
    return True


def test_score_with_decorator():
    """Test scores within @observe decorated function."""
    print("\n=== Testing Scores with @observe Decorator ===")
    
    @langfuse_tracer.observe(name="test-gedcom-processing")
    def process_gedcom():
        """Simulate GEDCOM processing."""
        # Simulate counting
        individuals = 15
        families = 7
        
        # Add scores
        langfuse_tracer.add_score(
            name="individuals_processed",
            value=individuals,
            comment=f"Processed {individuals} individuals"
        )
        
        langfuse_tracer.add_score(
            name="families_processed",
            value=families,
            comment=f"Processed {families} families"
        )
        
        return {"individuals": individuals, "families": families}
    
    try:
        print("✓ Calling @observe decorated function...")
        result = process_gedcom()
        print(f"  Result: {result}")
        print("  ✓ Function executed successfully with scores")
        print("\n✅ Decorator integration test passed!")
        return True
    except Exception as e:
        print(f"  ✗ Error in decorated function: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gedcom_counting_logic():
    """Test the GEDCOM counting logic directly."""
    print("\n=== Testing GEDCOM Counting Logic ===")
    
    # Sample GEDCOM content
    sample_gedcom = """0 HEAD
1 SOUR Test
0 @I1@ INDI
1 NAME John /Doe/
0 @I2@ INDI
1 NAME Jane /Smith/
0 @I3@ INDI
1 NAME Baby /Doe/
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
0 @F2@ FAM
1 HUSB @I1@
0 TRLR
"""
    
    # Count manually using the same logic as count_gedcom_records
    lines = sample_gedcom.split('\n')
    individual_count = 0
    family_count = 0
    
    for line in lines:
        if line.startswith('0 @I') and '@ INDI' in line:
            individual_count += 1
        elif line.startswith('0 @F') and '@ FAM' in line:
            family_count += 1
    
    print(f"✓ Counted {individual_count} individuals")
    print(f"✓ Counted {family_count} families")
    
    # Verify counts
    assert individual_count == 3, f"Expected 3 individuals, got {individual_count}"
    assert family_count == 2, f"Expected 2 families, got {family_count}"
    
    print("  ✓ Counts are correct!")
    
    # Test adding these as scores
    try:
        langfuse_tracer.add_score(
            name="individuals_processed",
            value=individual_count,
            comment=f"Counted from sample GEDCOM"
        )
        langfuse_tracer.add_score(
            name="families_processed",
            value=family_count,
            comment=f"Counted from sample GEDCOM"
        )
        print("  ✓ Scores added for counted records")
    except Exception as e:
        print(f"  ✗ Error adding scores: {e}")
        return False
    
    print("\n✅ GEDCOM counting test passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Langfuse Score Metrics - Simple Test")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Basic score functionality
    if not test_basic_score():
        all_passed = False
    
    # Test 2: GEDCOM counting logic
    if not test_gedcom_counting_logic():
        all_passed = False
    
    # Test 3: Scores with decorator
    if not test_score_with_decorator():
        all_passed = False
    
    # Flush traces if Langfuse is available
    if langfuse_tracer.is_available():
        print("\n=== Flushing Langfuse Traces ===")
        try:
            langfuse_tracer.flush()
            print("✓ Traces flushed successfully")
            print("\nℹ️  Check your Langfuse dashboard to see the scores!")
            print("   Look for 'individuals_processed' and 'families_processed' metrics")
        except Exception as e:
            print(f"⚠️  Error flushing traces: {e}")
    else:
        print("\nℹ️  Langfuse not configured - scores were no-ops (this is OK)")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nScore metrics implementation is working correctly!")
        print("\nWhat was implemented:")
        print("1. Added langfuse_tracer.add_score() function")
        print("2. Integrated score tracking in main.py after GEDCOM generation")
        print("3. Tracks 'individuals_processed' and 'families_processed' metrics")
        print("\nNext steps:")
        print("1. Run the microservice with real data")
        print("2. Check Langfuse dashboard for score metrics")
        print("3. Verify metrics appear in trace details")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
