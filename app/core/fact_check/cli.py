"""
Vanta: Fact-Check CLI (Layer 4)
Command line interface for fact-check API integration
"""

import argparse
import logging
import sys

from app.web.models import db
from app.web.models.verification import SocialMediaPost, Claim, VerificationResult, FactCheckSource
from app.core.fact_check.engine import create_fact_check_engine, verify_claim, batch_verify_claims
from app.core.fact_check.clients import GoogleFactCheckClient, MockFactCheckClient


def setup_logging():
    """Setup logging for CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_api_connection(args):
    """Test fact-check API connections"""
    print("Testing fact-check API connections...")
    
    if "google" in args.sources:
        print("\n1. Google Fact Check API:")
        client = GoogleFactCheckClient()
        
        if client.api_key and client.api_key != "your_google_fact_check_api_key_here":
            print(f"  ✅ API key configured: {client.api_key[:20]}...")
            
            # Test search
            try:
                results = client.search_claim("test claim", language="en")
                print(f"  ✅ API connection successful ({len(results)} test results)")
            except Exception as e:
                print(f"  ❌ API error: {e}")
        else:
            print(f"  ⚠️ API key not configured (check .env file)")
            print(f"  Add: GOOGLE_FACT_CHECK_API_KEY=your_key_here")
    
    if "mock" in args.sources:
        print("\n2. Mock Fact Check Client:")
        client = MockFactCheckClient()
        results = client.search_claim("test claim", language="en")
        print(f"  ✅ Mock client working ({len(results)} results)")
    
    print(f"\n✅ All configured sources tested")


def verify_single_claim(args):
    """Verify a single claim by ID"""
    print(f"Verifying claim: {args.claim_id}")
    
    result = verify_claim(args.claim_id)
    
    if not result:
        print(f"❌ Failed to verify claim {args.claim_id}")
        return
    
    print(f"\n✅ Verification complete:")
    print(f"  Claim ID: {result.claim_id}")
    print(f"  Status: {result.verification_status.value}")
    print(f"  Confidence: {result.confidence_score:.2f}")
    
    if result.fact_check_verdict:
        print(f"  Verdict: {result.fact_check_verdict}")
    
    if result.fact_check_sources:
        print(f"  Sources: {', '.join(result.fact_check_sources)}")


def batch_verify(args):
    """Batch verify unverified claims"""
    print(f"Batch verifying up to {args.limit} claims...")
    
    results = batch_verify_claims(args.limit)
    
    print(f"\n✅ Batch verification complete:")
    print(f"  Processed: {results['processed']}")
    print(f"  Successful: {results['successful']}")
    print(f"  Failed: {results['failed']}")


def view_results(args):
    """View verification results"""
    from app.web.models.verification import VerificationStatus
    
    # Get counts
    total_verifications = db.session.query(VerificationResult).count()
    
    # Count by status
    status_counts = {}
    for status in VerificationStatus:
        count = db.session.query(VerificationResult).filter_by(
            verification_status=status
        ).count()
        status_counts[status.value] = count
    
    # Get recent verifications
    recent = db.session.query(VerificationResult).order_by(
        VerificationResult.completed_at.desc()
    ).limit(10).all()
    
    print("📊 Fact-Check Results (Layer 4)")
    print("=" * 60)
    print(f"Total verifications: {total_verifications}")
    print()
    print("By status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    if recent:
        print(f"\nRecent verifications (last 10):")
        for ver in recent:
            claim = db.session.query(Claim).filter_by(id=ver.claim_id).first()
            claim_text_preview = claim.claim_text[:50] + "..." if claim else "???"
            
            print(f"\n  Claim: {claim_text_preview}")
            print(f"    Status: {ver.verification_status.value}")
            print(f"    Confidence: {ver.confidence_score:.2f}")
            if ver.fact_check_sources:
                print(f"    Sources: {ver.fact_check_sources}")


def register_fact_check_sources():
    """Register fact-check sources in database"""
    print("Registering fact-check sources...")
    
    sources = [
        {
            "id": "google_fact_check",
            "name": "Google Fact Check Tools",
            "url": "https://developers.google.com/fact-check/tools",
            "api_endpoint": "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            "api_key_required": True,
            "languages_supported": ["en", "es", "fr", "de", "pt", "hi", "bn", "ar", "ru", "ja", "ko", "zh"],
            "regions_covered": ["global"],
            "reliability_score": 0.9
        },
        {
            "id": "full_fact",
            "name": "Full Fact (UK)",
            "url": "https://fullfact.org",
            "api_endpoint": "https://fullfact.org/api",  # Note: May require registration
            "api_key_required": True,
            "languages_supported": ["en"],
            "regions_covered": ["GB", "UK"],
            "reliability_score": 0.85
        },
        {
            "id": "mock_fact_check",
            "name": "Mock Fact Checker (Development)",
            "url": "https://example.com",
            "api_endpoint": "",
            "api_key_required": False,
            "languages_supported": ["en", "bn"],
            "regions_covered": ["global"],
            "reliability_score": 0.5
        }
    ]
    
    registered = 0
    for source_data in sources:
        existing = db.session.query(FactCheckSource).filter_by(
            id=source_data["id"]
        ).first()
        
        if not existing:
            source = FactCheckSource(
                id=source_data["id"],
                name=source_data["name"],
                url=source_data["url"],
                api_endpoint=source_data["api_endpoint"],
                api_key_required=source_data["api_key_required"],
                languages_supported=source_data["languages_supported"],
                regions_covered=source_data["regions_covered"],
                reliability_score=source_data["reliability_score"],
                is_active=True
            )
            db.session.add(source)
            print(f"  ✅ Registered: {source_data['name']}")
            registered += 1
        else:
            print(f"  ⏭️ Already exists: {source_data['name']}")
    
    db.session.commit()
    print(f"\n✅ Registered {registered} new sources")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Vanta Fact-Check CLI (Layer 4)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Test API connections
    test_parser = subparsers.add_parser(
        "test",
        help="Test fact-check API connections"
    )
    test_parser.add_argument(
        "--sources",
        nargs="+",
        default=["google", "mock"],
        help="Sources to test"
    )
    
    # Verify single claim
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify a single claim"
    )
    verify_parser.add_argument(
        "claim_id",
        help="Claim ID to verify"
    )
    
    # Batch verify
    batch_parser = subparsers.add_parser(
        "batch",
        help="Batch verify unverified claims"
    )
    batch_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of claims to process"
    )
    
    # View results
    results_parser = subparsers.add_parser(
        "results",
        help="View verification results"
    )
    
    # Register sources
    register_parser = subparsers.add_parser(
        "register-sources",
        help="Register fact-check sources in database"
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "test":
        test_api_connection(args)
    elif args.command == "verify":
        verify_single_claim(args)
    elif args.command == "batch":
        batch_verify(args)
    elif args.command == "results":
        view_results(args)
    elif args.command == "register-sources":
        register_fact_check_sources()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()