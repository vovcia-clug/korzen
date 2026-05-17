#!/usr/bin/env python3
"""
Test to verify that the Pydantic models now match the prompt structure.
This simulates the exact structure returned by the LLM.
"""

import json
from src.models import ChurchRecordsDocument

# Sample JSON matching what the LLM returns (based on the prompt)
sample_json = {
    "records": [
        {
            "record_type": "baptism",
            "event_date": "1893-06-27",
            "event_place": "Test Parish",
            "person": {
                "given_names": "Vincentius",
                "surname": "Kowalski",
                "full_name": "Vincentius Kowalski",
                "gender": "M",
                "birth_date": "1893-06-27"
            },
            "parents": [
                {
                    "given_names": "Vincentius",
                    "surname": "Kowalski",
                    "full_name": "Vincentius Kowalski",
                    "role": "father"
                },
                {
                    "given_names": "Antonina",
                    "surname": "Santos",
                    "full_name": "Antonina Santos",
                    "role": "mother"
                }
            ],
            "witnesses": [
                {
                    "given_names": "Joannes",
                    "surname": "Novak",
                    "full_name": "Joannes Novak",
                    "role": "godfather"
                },
                {
                    "given_names": "Agatha",
                    "surname": "Smith",
                    "full_name": "Agatha Smith",
                    "role": "godmother"
                }
            ],
            "source_text": "Original Latin text...",
            "notes": "House number 123",
            "confidence": 0.95
        }
    ]
}

def test_model_parsing():
    """Test that the models can parse the LLM response structure."""
    try:
        # This should work now
        doc = ChurchRecordsDocument(**sample_json)
        
        print("✅ SUCCESS! Models can parse LLM response structure")
        print(f"   - Parsed {len(doc.records)} record(s)")
        print(f"   - Person: {doc.records[0].person.full_name}")
        print(f"   - Father: {doc.records[0].parents[0].full_name}")
        print(f"   - Mother: {doc.records[0].parents[1].full_name}")
        print(f"   - Godfather: {doc.records[0].witnesses[0].full_name}")
        print(f"   - Godmother: {doc.records[0].witnesses[1].full_name}")
        
        return True
        
    except Exception as e:
        print("❌ FAILED! Models cannot parse LLM response structure")
        print(f"   Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_model_parsing()
    exit(0 if success else 1)
