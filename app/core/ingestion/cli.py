"""
Vanta: Ingestion CLI
Command line interface for ingestion pipeline
"""

import sys
import argparse
import logging
from pathlib import Path

from app.web.models import db
from app.core.ingestion.ingestor import ApifyIngestor, ingest_apify_dataset, ingest_from_json_file


def setup_logging():
    """Setup logging for CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_tables():
    """Create database tables for verification pipeline"""
    from app.web.models.verification import (
        SocialMediaPost, 
        Claim, 
        VerificationResult,
        FactCheckSource,
        ExternalFactCheck
    )
    
    print("Creating verification tables...")
    
    # Import db from app.web.models
    from app.web.models import db
    
    # Create tables
    try:
        # This will create all tables defined in models
        db.create_all()
        print("✅ Tables created successfully")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        sys.exit(1)


def ingest_from_url(args):
    """Ingest from Apify dataset URL"""
    print(f"Fetching from Apify dataset: {args.url}")
    
    success, failed = ingest_apify_dataset(
        args.url,
        clean_mode=args.clean,
        max_posts=args.max_posts
    )
    
    print(f"Ingestion complete:")
    print(f"  ✅ Success: {success}")
    print(f"  ❌ Failed: {failed}")
    
    return success, failed


def ingest_from_file(args):
    """Ingest from local JSON file"""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ File not found: {args.file}")
        return
    
    print(f"Loading from file: {args.file}")
    
    success, failed = ingest_from_json_file(
        str(file_path),
        max_posts=args.max_posts
    )
    
    print(f"Ingestion complete:")
    print(f"  ✅ Success: {success}")
    print(f"  ❌ Failed: {failed}")
    
    return success, failed


def test_language_detection(args):
    """Test language detection"""
    from app.core.ingestion.lang_detect import detect_language
    
    if args.text:
        text = args.text
    else:
        # Example texts
        text_en = "The government announced new policies today."
        text_bn = "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।"
        text = text_bn if args.language == 'bn' else text_en
    
    lang_code, confidence = detect_language(text)
    
    print(f"Text: {text}")
    print(f"Detected language: {lang_code}")
    print(f"Confidence: {confidence}")
    
    return lang_code, confidence


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Vanta Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create tables command
    tables_parser = subparsers.add_parser(
        "create-tables",
        help="Create verification database tables"
    )
    
    # Ingestion from URL
    url_parser = subparsers.add_parser(
        "ingest-url",
        help="Ingest from Apify dataset URL"
    )
    url_parser.add_argument(
        "--url",
        required=True,
        help="Apify dataset URL"
    )
    url_parser.add_argument(
        "--clean",
        action="store_true",
        help="Use clean dataset format (stripped metadata)"
    )
    url_parser.add_argument(
        "--max-posts",
        type=int,
        help="Maximum number of posts to ingest"
    )
    
    # Ingestion from file
    file_parser = subparsers.add_parser(
        "ingest-file",
        help="Ingest from local JSON file"
    )
    file_parser.add_argument(
        "--file",
        required=True,
        help="Path to JSON file"
    )
    file_parser.add_argument(
        "--max-posts",
        type=int,
        help="Maximum number of posts to ingest"
    )
    
    # Test language detection
    lang_parser = subparsers.add_parser(
        "test-language",
        help="Test language detection"
    )
    lang_parser.add_argument(
        "--text",
        help="Text to analyze"
    )
    lang_parser.add_argument(
        "--language",
        choices=["en", "bn"],
        default="bn",
        help="Default language for example text"
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "create-tables":
        create_tables()
    elif args.command == "ingest-url":
        ingest_from_url(args)
    elif args.command == "ingest-file":
        ingest_from_file(args)
    elif args.command == "test-language":
        test_language_detection(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()