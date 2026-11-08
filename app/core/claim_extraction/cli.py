"""
Vanta: Claim Extraction CLI (Layer 3)
Command line interface for claim extraction pipeline
"""

import argparse
import logging
import sys

from app.web.models import db
from app.core.claim_extraction.extractor import ClaimExtractor, batch_extract_claims


def setup_logging():
    """Setup logging for CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_extraction(args):
    """Test claim extraction on sample text"""
    extractor = ClaimExtractor()
    
    sample_texts = {
        "bn": "গতকাল সরকার নতুন নীতি ঘোষণা করেছে। এই নীতির ফলে ১০ লক্ষ মানুষ উপকৃত হবে। আমি মনে করি এটি ভাল সিদ্ধান্ত।",
        "en": "The government announced new policies yesterday. This will benefit 1 million people. In my opinion, this is a good decision."
    }
    
    text = sample_texts["bn"] if args.language == "bn" else sample_texts["en"]
    
    print(f"Testing claim extraction on text:")
    print(f"Language: {args.language}")
    print(f"Text: {text}")
    print("-" * 60)
    
    claims = extractor.extract_claims_from_text(text, args.language)
    
    if not claims:
        print("No claims extracted")
        return
    
    for i, claim in enumerate(claims):
        print(f"Claim {i+1}:")
        print(f"  Text: {claim['claim_text']}")
        print(f"  Type: {claim['claim_type'].value}")
        print(f"  Checkworthiness: {claim['checkworthiness_score']:.2f}")
        print(f"  Entities: {[e['text'] for e in claim['entities']]}")
        print()


def process_posts(args):
    """Process unprocessed posts for claim extraction"""
    print(f"Processing up to {args.limit} unprocessed posts...")
    
    processed, claims = batch_extract_claims(args.limit)
    
    print(f"✅ Processed {processed} posts")
    print(f"✅ Extracted {claims} claims")
    
    return processed, claims


def view_statistics(args):
    """View claim extraction statistics"""
    from app.web.models.verification import SocialMediaPost, Claim
    
    # Get counts
    total_posts = db.session.query(SocialMediaPost).count()
    processed_posts = db.session.query(SocialMediaPost).filter_by(processed_for_claims=True).count()
    total_claims = db.session.query(Claim).count()
    
    # Count by claim type
    from app.web.models.verification import ClaimType
    claim_types = {}
    for claim_type in ClaimType:
        count = db.session.query(Claim).filter_by(claim_type=claim_type).count()
        claim_types[claim_type.value] = count
    
    print("📊 Claim Extraction Statistics")
    print("=" * 60)
    print(f"Total posts in database: {total_posts}")
    print(f"Posts processed for claims: {processed_posts}")
    print(f"Unprocessed posts: {total_posts - processed_posts}")
    print(f"Total claims extracted: {total_claims}")
    print()
    print("Claims by type:")
    for claim_type, count in claim_types.items():
        print(f"  {claim_type}: {count}")
    
    if total_posts > 0:
        print(f"Processing rate: {(processed_posts/total_posts)*100:.1f}%")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Vanta Claim Extraction CLI (Layer 3)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Test extraction
    test_parser = subparsers.add_parser(
        "test",
        help="Test claim extraction on sample text"
    )
    test_parser.add_argument(
        "--language",
        choices=["en", "bn"],
        default="bn",
        help="Language for sample text"
    )
    
    # Process posts
    process_parser = subparsers.add_parser(
        "process",
        help="Process unprocessed posts for claim extraction"
    )
    process_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of posts to process"
    )
    
    # View statistics
    stats_parser = subparsers.add_parser(
        "stats",
        help="View claim extraction statistics"
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "test":
        test_extraction(args)
    elif args.command == "process":
        process_posts(args)
    elif args.command == "stats":
        view_statistics(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()