#!/usr/bin/env python3
"""
Count Collection Pages Script
==============================

This script scans the S3 output bucket for OCR results and generates a report
showing page counts per collection/document, identifying missing pages and
providing completion status.

Usage:
    # Generate full report
    python count_collection_pages.py

    # Filter by S3 prefix (specific collection)
    python count_collection_pages.py --prefix ocr-results/documents/book-123/

    # Show only collections with missing pages
    python count_collection_pages.py --missing-only

    # Export report to JSON file
    python count_collection_pages.py --output report.json

    # Verbose output with detailed page listings
    python count_collection_pages.py --verbose

    # Sort by different criteria
    python count_collection_pages.py --sort-by completion  # or 'pages', 'missing', 'name'

Environment Variables:
    Required:
    - AWS_REGION: AWS region
    - AWS_ACCESS_KEY_ID: AWS access key (optional with IAM roles)
    - AWS_SECRET_ACCESS_KEY: AWS secret key (optional with IAM roles)
    - S3_OUTPUT_BUCKET: S3 output bucket name (for OCR results)
    
    Optional:
    - S3_OUTPUT_PREFIX: S3 output prefix (default: "ocr-results/")

Author: Page Counter Script Generator
Version: 1.0.0
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from dotenv import load_dotenv


class CounterScriptConfig:
    """Configuration for the counter script."""
    
    def __init__(self):
        """Load configuration from environment variables."""
        # Load .env file if it exists
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        
        # Required configuration
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.s3_output_bucket = os.getenv("S3_OUTPUT_BUCKET")
        
        # Optional configuration
        self.s3_output_prefix = os.getenv("S3_OUTPUT_PREFIX", "ocr-results/")
        if self.s3_output_prefix and not self.s3_output_prefix.endswith("/"):
            self.s3_output_prefix += "/"
        
        # Validate required configuration
        if not self.s3_output_bucket:
            raise ValueError("S3_OUTPUT_BUCKET environment variable is required")


class S3PageScanner:
    """Scans S3 bucket for OCR result files and extracts page information."""
    
    def __init__(self, config: CounterScriptConfig):
        """Initialize the S3 scanner.
        
        Args:
            config: Counter script configuration
        """
        self.config = config
        
        # Configure boto3 client
        boto_config = BotoConfig(
            region_name=config.aws_region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        
        # Create S3 client
        session_kwargs = {}
        if config.aws_access_key_id and config.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = config.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
        
        session = boto3.Session(**session_kwargs)
        self.s3_client = session.client("s3", config=boto_config)
    
    def extract_document_and_page(self, ocr_key: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Extract collection_id, document_id and page_number from OCR result S3 path.
        
        The path structure is: ocr-results/{collection-id}/{document-id}/{filename}.md
        We extract collection_id and document_id from the path and page_number from filename.
        
        Args:
            ocr_key: S3 key of the OCR result file
            
        Returns:
            Tuple of (collection_id, document_id, page_number) or (None, None, None) if extraction fails
        """
        # Remove the output prefix to get the relative path
        relative_path = ocr_key
        if ocr_key.startswith(self.config.s3_output_prefix):
            relative_path = ocr_key[len(self.config.s3_output_prefix):]
        
        # Get filename without extension
        path_obj = Path(relative_path)
        filename_base = path_obj.stem
        
        # Get parent directory structure
        parent_parts = path_obj.parent.parts
        
        # Extract collection_id and document_id from path
        collection_id = None
        document_id = None
        
        if len(parent_parts) >= 2:
            # Path structure: collection-id/document-id/filename.md
            collection_id = parent_parts[0]
            document_id = parent_parts[-1]
        elif len(parent_parts) == 1:
            # Only one directory level - use as document_id
            document_id = parent_parts[0]
            collection_id = parent_parts[0]
        else:
            # No parent directory - use filename as document_id
            document_id = filename_base
            collection_id = filename_base
        
        # Try to extract page number from filename
        # Patterns: page-005, page_005, 005, p005, etc.
        page_match = re.search(r'(?:page[-_]?)?(\d+)', filename_base, re.IGNORECASE)
        if page_match:
            try:
                page_number = int(page_match.group(1))
            except ValueError:
                page_number = None
        else:
            page_number = None
        
        return collection_id, document_id, page_number
    
    def scan_all_pages(
        self,
        prefix: Optional[str] = None,
    ) -> Dict[str, Dict[str, any]]:
        """Scan S3 output bucket and collect all pages per document.
        
        Args:
            prefix: Optional S3 prefix to filter objects
            
        Returns:
            Dictionary mapping document_id to dict with collection_id and set of page numbers
        """
        # Use provided prefix or default output prefix
        if prefix:
            scan_prefix = prefix
        else:
            scan_prefix = self.config.s3_output_prefix
        
        print(f"Scanning S3 output bucket: s3://{self.config.s3_output_bucket}/{scan_prefix}")
        
        document_pages = defaultdict(lambda: {"collection_id": None, "pages": set(), "s3_path": None})
        total_files = 0
        skipped_files = 0
        
        paginator = self.s3_client.get_paginator("list_objects_v2")
        
        try:
            page_iterator = paginator.paginate(
                Bucket=self.config.s3_output_bucket,
                Prefix=scan_prefix,
            )
            
            for page in page_iterator:
                if "Contents" not in page:
                    continue
                
                for obj in page["Contents"]:
                    # Filter by .md extension
                    key = obj["Key"]
                    if not key.endswith(".md"):
                        continue
                    
                    total_files += 1
                    
                    # Extract collection_id, document_id and page_number
                    collection_id, document_id, page_number = self.extract_document_and_page(key)
                    
                    if document_id and page_number is not None:
                        document_pages[document_id]["collection_id"] = collection_id
                        document_pages[document_id]["pages"].add(page_number)
                        # Store S3 path (parent directory of the file)
                        if document_pages[document_id]["s3_path"] is None:
                            s3_parent = str(Path(key).parent)
                            document_pages[document_id]["s3_path"] = f"s3://{self.config.s3_output_bucket}/{s3_parent}/"
                    else:
                        skipped_files += 1
            
            print(f"Found {total_files} OCR result files")
            print(f"Identified {len(document_pages)} unique collections/documents")
            if skipped_files > 0:
                print(f"Skipped {skipped_files} files (could not extract page number)")
            
            return dict(document_pages)
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"Error scanning output bucket: {error_code} - {e}")
            raise


class PageAnalyzer:
    """Analyzes page data to identify missing pages and generate statistics."""
    
    @staticmethod
    def analyze_document(document_id: str, pages: Set[int]) -> Dict:
        """Analyze a single document's pages.
        
        Args:
            document_id: Document identifier
            pages: Set of page numbers found
            
        Returns:
            Dictionary with analysis results
        """
        if not pages:
            return {
                "document_id": document_id,
                "total_pages": 0,
                "page_range": None,
                "missing_pages": [],
                "missing_count": 0,
                "completion_percentage": 0.0,
                "status": "empty"
            }
        
        sorted_pages = sorted(pages)
        min_page = sorted_pages[0]
        max_page = sorted_pages[-1]
        expected_pages = max_page - min_page + 1
        actual_pages = len(pages)
        
        # Find missing pages
        expected_set = set(range(min_page, max_page + 1))
        missing_pages = sorted(expected_set - pages)
        missing_count = len(missing_pages)
        
        # Calculate completion percentage
        completion_percentage = (actual_pages / expected_pages * 100) if expected_pages > 0 else 0.0
        
        # Determine status
        if missing_count == 0:
            status = "complete"
        elif completion_percentage >= 90:
            status = "mostly_complete"
        elif completion_percentage >= 50:
            status = "partial"
        else:
            status = "incomplete"
        
        return {
            "document_id": document_id,
            "total_pages": actual_pages,
            "page_range": f"{min_page}-{max_page}",
            "expected_pages": expected_pages,
            "missing_pages": missing_pages,
            "missing_count": missing_count,
            "completion_percentage": round(completion_percentage, 2),
            "status": status,
            "pages": sorted_pages
        }
    
    @staticmethod
    def analyze_all_documents(document_pages: Dict[str, Dict[str, any]]) -> List[Dict]:
        """Analyze all documents.
        
        Args:
            document_pages: Dictionary mapping document_id to dict with collection_id and set of page numbers
            
        Returns:
            List of analysis results for all documents
        """
        results = []
        for document_id, data in document_pages.items():
            pages = data["pages"]
            collection_id = data["collection_id"]
            s3_path = data.get("s3_path")
            analysis = PageAnalyzer.analyze_document(document_id, pages)
            analysis["collection_id"] = collection_id
            analysis["s3_path"] = s3_path
            results.append(analysis)
        
        return results


class ReportGenerator:
    """Generates formatted reports from page analysis."""
    
    @staticmethod
    def print_summary(analyses: List[Dict]):
        """Print summary statistics.
        
        Args:
            analyses: List of document analyses
        """
        if not analyses:
            print("\nNo documents found.")
            return
        
        total_documents = len(analyses)
        total_pages = sum(a["total_pages"] for a in analyses)
        complete_docs = sum(1 for a in analyses if a["status"] == "complete")
        incomplete_docs = sum(1 for a in analyses if a["missing_count"] > 0)
        total_missing = sum(a["missing_count"] for a in analyses)
        
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        print(f"Total Collections/Documents: {total_documents}")
        print(f"Total Pages Uploaded: {total_pages}")
        print(f"Complete Documents: {complete_docs} ({complete_docs/total_documents*100:.1f}%)")
        print(f"Documents with Missing Pages: {incomplete_docs}")
        print(f"Total Missing Pages: {total_missing}")
        print()
    
    @staticmethod
    def print_detailed_report(
        analyses: List[Dict],
        missing_only: bool = False,
        verbose: bool = False,
        sort_by: str = "name"
    ):
        """Print detailed report for each document.
        
        Args:
            analyses: List of document analyses
            missing_only: Only show documents with missing pages
            verbose: Show detailed page listings
            sort_by: Sort criteria ('name', 'pages', 'missing', 'completion')
        """
        # Filter if needed
        if missing_only:
            analyses = [a for a in analyses if a["missing_count"] > 0]
        
        # Sort analyses
        if sort_by == "pages":
            analyses = sorted(analyses, key=lambda x: x["total_pages"], reverse=True)
        elif sort_by == "missing":
            analyses = sorted(analyses, key=lambda x: x["missing_count"], reverse=True)
        elif sort_by == "completion":
            analyses = sorted(analyses, key=lambda x: x["completion_percentage"])
        else:  # name
            analyses = sorted(analyses, key=lambda x: x["document_id"])
        
        print("=" * 80)
        print("DETAILED REPORT")
        print("=" * 80)
        print()
        
        for i, analysis in enumerate(analyses, 1):
            # Status emoji
            status_emoji = {
                "complete": "✓",
                "mostly_complete": "⚠",
                "partial": "⚠",
                "incomplete": "✗",
                "empty": "✗"
            }.get(analysis["status"], "?")
            
            print(f"{i}. {status_emoji} {analysis['document_id']}")
            print(f"   {'─' * 76}")
            if analysis.get("collection_id"):
                print(f"   Collection ID: {analysis['collection_id']}")
            if analysis.get("s3_path"):
                print(f"   S3 Path: {analysis['s3_path']}")
            print(f"   Total Pages Uploaded: {analysis['total_pages']}")
            
            if analysis["page_range"]:
                print(f"   Page Range: {analysis['page_range']} (expected: {analysis['expected_pages']} pages)")
                print(f"   Completion: {analysis['completion_percentage']}%")
                
                if analysis["missing_count"] > 0:
                    print(f"   Missing Pages: {analysis['missing_count']}")
                    
                    # Show missing pages (limit to first 20 if not verbose)
                    missing = analysis["missing_pages"]
                    if verbose or len(missing) <= 20:
                        print(f"   Missing Page Numbers: {', '.join(map(str, missing))}")
                    else:
                        print(f"   Missing Page Numbers: {', '.join(map(str, missing[:20]))}... (and {len(missing)-20} more)")
                else:
                    print(f"   Status: Complete ✓")
            else:
                print(f"   Status: No pages found")
            
            # Show all pages if verbose
            if verbose and analysis.get("pages"):
                pages = analysis["pages"]
                if len(pages) <= 50:
                    print(f"   All Pages: {', '.join(map(str, pages))}")
                else:
                    print(f"   All Pages: {', '.join(map(str, pages[:50]))}... (and {len(pages)-50} more)")
            
            print()
    
    @staticmethod
    def export_json(analyses: List[Dict], output_file: str):
        """Export report to JSON file.
        
        Args:
            analyses: List of document analyses
            output_file: Output file path
        """
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_documents": len(analyses),
            "total_pages": sum(a["total_pages"] for a in analyses),
            "complete_documents": sum(1 for a in analyses if a["status"] == "complete"),
            "total_missing_pages": sum(a["missing_count"] for a in analyses),
            "documents": analyses
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Report exported to: {output_file}")


def main():
    """Main entry point for the counter script."""
    parser = argparse.ArgumentParser(
        description="Count pages per collection and identify missing pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate full report
  python count_collection_pages.py

  # Filter by S3 prefix (specific collection)
  python count_collection_pages.py --prefix ocr-results/documents/book-123/

  # Show only collections with missing pages
  python count_collection_pages.py --missing-only

  # Export report to JSON file
  python count_collection_pages.py --output report.json

  # Verbose output with detailed page listings
  python count_collection_pages.py --verbose

  # Sort by completion percentage
  python count_collection_pages.py --sort-by completion
        """
    )
    
    parser.add_argument(
        "--prefix",
        type=str,
        help="S3 prefix to filter objects (e.g., 'ocr-results/documents/book-123/')"
    )
    
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Show only documents with missing pages"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Export report to JSON file"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with detailed page listings"
    )
    
    parser.add_argument(
        "--sort-by",
        choices=["name", "pages", "missing", "completion"],
        default="name",
        help="Sort documents by: name (default), pages (count), missing (count), or completion (percentage)"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("=" * 80)
    print("OCR Image Microservice - Count Collection Pages Script")
    print("=" * 80)
    print()
    
    try:
        # Load configuration
        print("Loading configuration...")
        config = CounterScriptConfig()
        print(f"  S3 Output Bucket: {config.s3_output_bucket}")
        print(f"  S3 Output Prefix: {config.s3_output_prefix}")
        print()
        
        # Initialize components
        scanner = S3PageScanner(config)
        
        # Step 1: Scan S3 bucket for all pages
        print("Step 1: Scanning S3 bucket for OCR results...")
        document_pages = scanner.scan_all_pages(prefix=args.prefix)
        print()
        
        if not document_pages:
            print("No documents found matching the criteria.")
            return 0
        
        # Step 2: Analyze pages
        print("Step 2: Analyzing page data...")
        analyses = PageAnalyzer.analyze_all_documents(document_pages)
        print(f"Analyzed {len(analyses)} documents")
        print()
        
        # Step 3: Generate report
        print("Step 3: Generating report...")
        print()
        
        # Print summary
        ReportGenerator.print_summary(analyses)
        
        # Print detailed report
        ReportGenerator.print_detailed_report(
            analyses,
            missing_only=args.missing_only,
            verbose=args.verbose,
            sort_by=args.sort_by
        )
        
        # Export to JSON if requested
        if args.output:
            ReportGenerator.export_json(analyses, args.output)
            print()
        
        print("=" * 80)
        print("Report generation complete!")
        print("=" * 80)
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        return 130
        
    except Exception as e:
        print(f"Fatal error: {e}")
        if args.verbose if 'args' in locals() else False:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
