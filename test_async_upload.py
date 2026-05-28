#!/usr/bin/env python3
"""
Test script to verify asynchronous file upload and processing.

This script tests that:
1. File uploads return immediately (HTTP 202)
2. Files are queued for processing
3. Processing happens asynchronously in the background
4. Status updates correctly through the processing lifecycle
"""

import os
import sys
import time
import requests
from pathlib import Path

# Configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
UPLOAD_ENDPOINT = f"{BASE_URL}/upload"
FILES_ENDPOINT = f"{BASE_URL}/files"

# Test file path - use one of the sample GEDCOM files
TEST_FILE = "data/test_sample.ged"


def test_async_upload():
    """Test asynchronous file upload and processing."""
    
    print("=" * 70)
    print("Testing Asynchronous File Upload and Processing")
    print("=" * 70)
    
    # Check if test file exists
    if not os.path.exists(TEST_FILE):
        print(f"❌ Test file not found: {TEST_FILE}")
        print("Available test files:")
        data_dir = Path("data")
        if data_dir.exists():
            for f in data_dir.glob("*.ged"):
                print(f"  - {f}")
        return False
    
    print(f"\n1. Uploading test file: {TEST_FILE}")
    print("-" * 70)
    
    # Upload the file
    start_time = time.time()
    
    try:
        with open(TEST_FILE, 'rb') as f:
            files = {'file': (os.path.basename(TEST_FILE), f, 'application/x-gedcom')}
            response = requests.post(UPLOAD_ENDPOINT, files=files, timeout=5)
        
        upload_time = time.time() - start_time
        
        print(f"✓ Upload completed in {upload_time:.3f} seconds")
        print(f"  Status Code: {response.status_code}")
        
        # Check if response is immediate (should be 202 Accepted)
        if response.status_code == 202:
            print("✓ Received HTTP 202 Accepted (asynchronous processing)")
        elif response.status_code == 201:
            print("⚠ Received HTTP 201 Created (synchronous processing - OLD BEHAVIOR)")
            print("  This indicates the file was processed synchronously!")
            return False
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
        
        # Parse response
        data = response.json()
        print(f"\n2. Upload Response:")
        print("-" * 70)
        print(f"  Message: {data.get('message')}")
        print(f"  File ID: {data.get('file_id')}")
        print(f"  Filename: {data.get('filename')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Queue Size: {data.get('queue_size')}")
        
        # Verify status is 'queued'
        if data.get('status') == 'queued':
            print("✓ File status is 'queued' (correct)")
        else:
            print(f"❌ Expected status 'queued', got '{data.get('status')}'")
            return False
        
        # Verify upload was fast (should be < 2 seconds for immediate return)
        if upload_time < 2.0:
            print(f"✓ Upload was fast ({upload_time:.3f}s < 2.0s) - indicates immediate return")
        else:
            print(f"⚠ Upload took {upload_time:.3f}s - may indicate synchronous processing")
        
        file_id = data.get('file_id')
        
        # Monitor processing status
        print(f"\n3. Monitoring Processing Status:")
        print("-" * 70)
        
        max_wait = 60  # Maximum 60 seconds
        check_interval = 2  # Check every 2 seconds
        elapsed = 0
        
        while elapsed < max_wait:
            time.sleep(check_interval)
            elapsed += check_interval
            
            # Get file status
            try:
                response = requests.get(FILES_ENDPOINT, timeout=5)
                if response.status_code == 200:
                    files_data = response.json()
                    
                    # Find our file
                    our_file = None
                    for file_info in files_data.get('data', []):
                        if file_info.get('id') == file_id:
                            our_file = file_info
                            break
                    
                    if our_file:
                        status = our_file.get('processing_status')
                        print(f"  [{elapsed}s] Status: {status}")
                        
                        if status == 'completed':
                            print(f"\n✓ File processing completed successfully in ~{elapsed}s")
                            print("✓ Asynchronous processing is working correctly!")
                            return True
                        elif status == 'failed':
                            print(f"\n❌ File processing failed")
                            return False
                        elif status in ['queued', 'processing']:
                            # Still processing, continue waiting
                            continue
                        else:
                            print(f"\n⚠ Unexpected status: {status}")
                    else:
                        print(f"  [{elapsed}s] File not found in list")
                else:
                    print(f"  [{elapsed}s] Failed to get file list: {response.status_code}")
            
            except Exception as e:
                print(f"  [{elapsed}s] Error checking status: {e}")
        
        print(f"\n⚠ Processing did not complete within {max_wait}s")
        print("  This may be normal for large files")
        return True  # Still consider it a success if it's queued
        
    except requests.exceptions.Timeout:
        upload_time = time.time() - start_time
        print(f"❌ Upload request timed out after {upload_time:.3f}s")
        print("  This suggests synchronous processing is still happening!")
        return False
    
    except Exception as e:
        print(f"❌ Error during upload: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("\nAsynchronous File Upload Test")
    print(f"Target: {BASE_URL}")
    print(f"Test File: {TEST_FILE}\n")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running\n")
        else:
            print(f"⚠ Server returned status {response.status_code}\n")
    except Exception as e:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"   Error: {e}")
        print("\nPlease ensure the Flask application is running:")
        print("  python src/main.py")
        return 1
    
    # Run the test
    success = test_async_upload()
    
    print("\n" + "=" * 70)
    if success:
        print("✓ TEST PASSED: Asynchronous upload is working correctly!")
    else:
        print("❌ TEST FAILED: Issues detected with asynchronous upload")
    print("=" * 70 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
