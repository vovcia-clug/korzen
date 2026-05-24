#!/usr/bin/env python3
"""Test script to verify composite document ID generation."""

import re
from pathlib import Path
from typing import Dict

def extract_from_s3_path(s3_uri: str) -> Dict[str, any]:
    """
    Extract document_id and page_number from S3 URI path patterns.
    
    For powiat scanning with multiple collections, generates composite document IDs
    to prevent collisions when different collections have units with the same numbers.
    """
    metadata = {}
    
    try:
        # Extract the path part after bucket
        match = re.match(r's3://[^/]+/(.+)', s3_uri)
        if not match:
            print(f"  ❌ Could not parse S3 URI: {s3_uri}")
            return metadata
        
        path = match.group(1)
        parts = path.split('/')
        filename = parts[-1]
        
        metadata['filename'] = filename
        
        # Try to extract page number from filename
        page_patterns = [
            r'page[-_](\d+)',  # page-005 or page_005
            r'p(\d+)',         # p005
            r'^(\d+)\.',       # 005.jpg (number at start)
        ]
        
        for pattern in page_patterns:
            page_match = re.search(pattern, filename, re.IGNORECASE)
            if page_match:
                page_number = int(page_match.group(1))
                metadata['page_number'] = page_number
                break
        
        # Extract document_id with collection context to prevent ID collisions
        # For powiat structure: powiat/collection_id/unit_number/file.jpg
        if len(parts) >= 3:
            # Check if this looks like a powiat/collection/unit structure
            potential_collection = parts[-3]
            potential_unit = parts[-2]
            
            # If both look like numeric IDs, create composite document_id
            if potential_collection.isdigit() and potential_unit.isdigit():
                collection_id = potential_collection
                unit_number = potential_unit
                document_id = f"{collection_id}-{unit_number}"
                
                metadata['collection_id'] = collection_id
                metadata['unit_number'] = unit_number
                metadata['document_id'] = document_id
            else:
                # Not a powiat structure, use parent directory as document_id
                document_id = parts[-2]
                metadata['document_id'] = document_id
        elif len(parts) >= 2:
            # Simple structure: use parent directory as document_id
            document_id = parts[-2]
            metadata['document_id'] = document_id
        
        # If path has more structure, try to find a better document_id
        # Only override if we haven't already found a composite ID
        if 'collection_id' not in metadata:
            for i, part in enumerate(parts[:-1]):
                if part in ['documents', 'books', 'records', 'images']:
                    if i + 1 < len(parts):
                        document_id = parts[i + 1]
                        metadata['document_id'] = document_id
                        break
        
    except Exception as e:
        print(f"  ❌ Error extracting metadata: {e}")
    
    return metadata


def test_metadata_extraction():
    """Test the metadata extraction with various S3 URI patterns."""
    
    test_cases = [
        {
            'uri': 's3://bucket/uploads/krakowski/1784/3500/001.jpg',
            'expected_doc_id': '1784-3500',
            'expected_collection': '1784',
            'expected_unit': '3500',
            'expected_page': 1,
        },
        {
            'uri': 's3://bucket/uploads/krakowski/1885/3500/002.jpg',
            'expected_doc_id': '1885-3500',
            'expected_collection': '1885',
            'expected_unit': '3500',
            'expected_page': 2,
        },
        {
            'uri': 's3://bucket/uploads/1784/4500/010.jpg',
            'expected_doc_id': '1784-4500',
            'expected_collection': '1784',
            'expected_unit': '4500',
            'expected_page': 10,
        },
        {
            'uri': 's3://bucket/uploads/3500/001.jpg',
            'expected_doc_id': '3500',
            'expected_collection': None,
            'expected_unit': None,
            'expected_page': 1,
        },
        {
            'uri': 's3://bucket/documents/book-123/page-005.jpg',
            'expected_doc_id': 'book-123',
            'expected_collection': None,
            'expected_unit': None,
            'expected_page': 5,
        },
    ]
    
    print('Testing OCR Metadata Extractor - Composite Document ID Generation')
    print('=' * 80)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f'\nTest {i}: {test["uri"]}')
        
        metadata = extract_from_s3_path(test['uri'])
        
        # Check document_id
        if metadata.get('document_id') == test['expected_doc_id']:
            print(f'  ✅ document_id: {metadata["document_id"]}')
            passed += 1
        else:
            print(f'  ❌ document_id: got {metadata.get("document_id")}, expected {test["expected_doc_id"]}')
            failed += 1
        
        # Check collection_id
        if test['expected_collection']:
            if metadata.get('collection_id') == test['expected_collection']:
                print(f'  ✅ collection_id: {metadata["collection_id"]}')
            else:
                print(f'  ❌ collection_id: got {metadata.get("collection_id")}, expected {test["expected_collection"]}')
        
        # Check unit_number
        if test['expected_unit']:
            if metadata.get('unit_number') == test['expected_unit']:
                print(f'  ✅ unit_number: {metadata["unit_number"]}')
            else:
                print(f'  ❌ unit_number: got {metadata.get("unit_number")}, expected {test["expected_unit"]}')
        
        # Check page_number
        if metadata.get('page_number') == test['expected_page']:
            print(f'  ✅ page_number: {metadata["page_number"]}')
        else:
            print(f'  ❌ page_number: got {metadata.get("page_number")}, expected {test["expected_page"]}')
    
    print('\n' + '=' * 80)
    print(f'Results: {passed} passed, {failed} failed')
    
    if failed == 0:
        print('✅ All tests passed! Composite document ID generation works correctly.')
    else:
        print(f'❌ {failed} test(s) failed.')
    
    return failed == 0


if __name__ == '__main__':
    success = test_metadata_extraction()
    exit(0 if success else 1)
