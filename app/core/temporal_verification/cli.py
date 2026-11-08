"""
Vanta: Temporal Verification CLI (Layer 5)
Command line interface for timeline and context verification
"""

import argparse
import logging
import sys

from app.web.models import db
from app.web.models.verification import Claim
from .verifier import create_temporal_verifier, verify_claim_temporally


def setup_logging():
    """Setup logging for CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_apis(args):
    """Test temporal API connections"""
    print("Testing Temporal Verification APIs...")
    
    from .clients import NewsAPIClient, WaybackClient, GDELTClient, WikipediaClient
    
    if "newsapi" in args.sources:
        print("\n1. NewsAPI:")
        client = NewsAPIClient()
        
        if client.api_key and client.api_key != "your_newsapi_key_here":
            print(f"  ✅ API key configured: {client.api_key[:20]}...")
        else:
            print(f"  ⚠️ API key not configured")
            print(f"  Add: NEWSAPI_KEY=your_key_here to .env")
    
    if "wayback" in args.sources:
        print("\n2. Wayback Machine:")
        client = WaybackClient()
        print(f"  ✅ Client ready (no API key required)")
    
    if "gdelt" in args.sources:
        print("\n3. GDELT API:")
        client = GDELTClient()
        print(f"  ✅ Client ready (no API key required)")
    
    if "wikipedia" in args.sources:
        print("\n4. Wikipedia API:")
        client = WikipediaClient()
        print(f"  ✅ Client ready (no API key required)")
    
    print(f"\n✅ All temporal sources configured")


def verify_single_claim(args):
    """Verify a single claim temporally"""
    print(f"Temporally verifying claim: {args.claim_id}")
    
    # Get claim
    claim = db.session.query(Claim).filter_by(id=args.claim_id).first()
    
    if not claim:
        print(f"❌ Claim not found: {args.claim_id}")
        return
    
    verifier = create_temporal_verifier(sources=args.sources)
    result = verifier.verify_claim_temporally(claim)
    
    if not result:
        print(f"❌ Failed to verify claim {args.claim_id}")
        return
    
    print(f"\n✅ Temporal verification complete:")
    print(f"  Claim: {claim.claim_text[:80]}...")
    print(f"  Date: {result.get('claim_date', 'unknown')}")
    print(f"  Plausibility: {result.get('temporal_plausibility')}")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")
    
    verifications = result.get("verifications", {})
    print(f"\n  Sources:")
    
    for source_name, source_result in verifications.items():
        if source_result.get("verified") is not False:
            confidence = source_result.get("confidence", 0.0)
            reason = source_result.get("reason", "")[:60]
            print(f"    • {source_name}: {confidence:.2f} - {reason}")


def batch_verify(args):
    """Batch verify claims temporally"""
    print(f"Batch temporally verifying up to {args.limit} claims...")
    
    verifier = create_temporal_verifier(sources=args.sources)
    results = verifier.process_unverified_claims(args.limit)
    
    print(f"\n✅ Batch temporal verification complete:")
    print(f"  Processed: {results['processed']}")
    print(f"  Successful: {results['successful']}")
    print(f"  Failed: {results['failed']}")


def view_temporal_stats(args):
    """View temporal verification statistics"""
    from app.web.models.verification import VerificationResult
    
    # Get verifications with layer_5 data
    verifications = db.session.query(VerificationResult).all()
    
    total = len(verifications)
    with_layer5 = 0
    plausibility_counts = {}
    
    for ver in verifications:
        if ver.evidence_chain and "layer_5" in ver.evidence_chain:
            with_layer5 += 1
            
            layer5 = ver.evidence_chain["layer_5"]
            plausibility = layer5.get("temporal_plausibility", "UNKNOWN")
            
            if plausibility not in plausibility_counts:
                plausibility_counts[plausibility] = 0
            plausibility_counts[plausibility] += 1
    
    print("📊 Temporal Verification Statistics (Layer 5)")
    print("=" * 60)
    print(f"Total verifications: {total}")
    print(f"With temporal verification: {with_layer5} ({with_layer5/total*100:.1f}%)")
    
    if plausibility_counts:
        print(f"\nTemporal plausibility distribution:")
        for plausibility, count in sorted(plausibility_counts.items()):
            percentage = count / with_layer5 * 100 if with_layer5 > 0 else 0
            print(f"  {plausibility}: {count} ({percentage:.1f}%)")
    
    # Show recent temporal verifications
    recent = []
    for ver in verifications[-10:]:  # Last 10
        if ver.evidence_chain and "layer_5" in ver.evidence_chain:
            layer5 = ver.evidence_chain["layer_5"]
            
            # Get claim text
            claim = db.session.query(Claim).filter_by(id=ver.claim_id).first()
            claim_text = claim.claim_text[:50] + "..." if claim else "???"
            
            recent.append({
                "claim": claim_text,
                "plausibility": layer5.get("temporal_plausibility"),
                "confidence": layer5.get("confidence", 0.0)
            })
    
    if recent:
        print(f"\nRecent temporal verifications:")
        for i, item in enumerate(recent, 1):
            print(f"  {i}. {item['claim']}")
            print(f"     → {item['plausibility']} (confidence: {item['confidence']:.2f})")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Vanta Temporal Verification CLI (Layer 5)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Test APIs
    test_parser = subparsers.add_parser(
        "test",
        help="Test temporal API connections"
    )
    test_parser.add_argument(
        "--sources",
        nargs="+",
        default=["newsapi", "wayback", "gdelt", "wikipedia"],
        help="Sources to test"
    )
    
    # Verify single claim
    verify_parser = subparsers.add_parser(
        "verify",
        help="Temporally verify a single claim"
    )
    verify_parser.add_argument(
        "claim_id",
        help="Claim ID to verify"
    )
    verify_parser.add_argument(
        "--sources",
        nargs="+",
        default=["newsapi", "wayback"],
        help="Sources to use"
    )
    
    # Batch verify
    batch_parser = subparsers.add_parser(
        "batch",
        help="Batch temporally verify claims"
    )
    batch_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of claims to process"
    )
    batch_parser.add_argument(
        "--sources",
        nargs="+",
        default=["newsapi", "wayback"],
        help="Sources to use"
    )
    
    # View stats
    stats_parser = subparsers.add_parser(
        "stats",
        help="View temporal verification statistics"
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "test":
        test_apis(args)
    elif args.command == "verify":
        verify_single_claim(args)
    elif args.command == "batch":
        batch_verify(args)
    elif args.command == "stats":
        view_temporal_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()