"""
Vanta: Layer 7 CLI - Confidence Scoring & Human Review
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.core.evidence.models import Claim, VerificationStatus
from app.core.evidence.credibility import CredibilityScorer
from app.core.evidence.confidence_scorer import ConfidenceScorer, ConfidenceBreakdown


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Vanta.Layer7.CLI")


def score_credibility(args):
    """Score source credibility"""
    scorer = CredibilityScorer()
    
    urls = args.urls or ["reuters.com", "infowars.com", "unknown-blog.com", "bbc.com"]
    
    print("Source Credibility Scores")
    print("=" * 70)
    
    for url in urls:
        profile = scorer.score_source(url)
        print(f"\n{url}")
        print(f"  Name: {profile.name}")
        print(f"  Score: {profile.credibility_score:.2f}")
        print(f"  Tier: {profile.tier.value}")
        print(f"  Type: {profile.source_type}")
        if profile.bias_rating:
            print(f"  Bias: {profile.bias_rating}")
        if profile.notes:
            print(f"  Notes: {profile.notes}")


def score_confidence(args):
    """Calculate confidence scores from evidence chain JSON"""
    scorer = ConfidenceScorer()
    
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        # Demo data
        data = {
            "claim_id": "demo_claim",
            "confidence_score": 0.75,
            "evidence_chain": {
                "layer_4": {
                    "matches_found": 3,
                    "verifications": {"sources_queried": ["google_fact_check", "snopes"]}
                },
                "layer_5": {
                    "confidence": 0.6,
                    "sources_used": ["newsapi", "gdelt", "wayback"],
                    "verifications": {
                        "news": {"total_articles": 5, "articles": [{"source_name": "Reuters"}]},
                        "events": {"total_events": 2}
                    }
                },
                "layer_6": {
                    "confidence": 0.8,
                    "grounding_score": 0.85,
                    "evidence_count": 8
                }
            }
        }
    
    # Create mock verification object
    class MockVerification:
        def __init__(self, data):
            self.claim_id = data.get("claim_id", "")
            self.confidence_score = data.get("confidence_score", 0.0)
            self.evidence_chain = data.get("evidence_chain", {})
            self.verification_status = VerificationStatus.UNVERIFIED
    
    verification = MockVerification(data)
    result = scorer.score_verification(verification)
    
    print("\nConfidence Scoring Results")
    print("=" * 70)
    print(f"Verdict: {result['verdict']}")
    print(f"Composite Score: {result['confidence_score']:.3f}")
    print(f"Needs Human Review: {result['needs_human_review']}")
    
    print("\nBreakdown:")
    breakdown = result['breakdown']
    for key, value in breakdown.items():
        if isinstance(value, float):
            bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
            print(f"  {key:25s} {bar} {value:.3f}")


def batch_score(args):
    """Batch score verification results"""
    scorer = ConfidenceScorer()
    
    input_dir = Path(args.input_dir) if args.input_dir else Path("data/verifications")
    
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return
    
    results = []
    
    for json_file in input_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            class MockVerification:
                def __init__(self, d):
                    self.claim_id = d.get("claim_id", "")
                    self.confidence_score = d.get("confidence_score", 0.0)
                    self.evidence_chain = d.get("evidence_chain", {})
                    self.verification_status = VerificationStatus.UNVERIFIED
            
            verification = MockVerification(data)
            result = scorer.score_verification(verification)
            result["file"] = json_file.name
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
    
    print(f"\nProcessed {len(results)} verification files")
    print("=" * 70)
    
    # Summary statistics
    verdicts = {}
    needs_review = 0
    
    for r in results:
        verdict = r["verdict"]
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        if r["needs_human_review"]:
            needs_review += 1
    
    print(f"\nVerdict Distribution:")
    for verdict, count in sorted(verdicts.items()):
        print(f"  {verdict}: {count}")
    
    print(f"\nNeeds Human Review: {needs_review}/{len(results)}")
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


def review_queue(args):
    """Show claims needing human review"""
    scorer = ConfidenceScorer()
    
    input_dir = Path(args.input_dir) if args.input_dir else Path("data/verifications")
    
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return
    
    review_items = []
    
    for json_file in input_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            class MockVerification:
                def __init__(self, d):
                    self.claim_id = d.get("claim_id", "")
                    self.confidence_score = d.get("confidence_score", 0.0)
                    self.evidence_chain = d.get("evidence_chain", {})
                    self.verification_status = VerificationStatus.UNVERIFIED
            
            verification = MockVerification(data)
            result = scorer.score_verification(verification)
            
            if result["needs_human_review"]:
                result["file"] = json_file.name
                review_items.append(result)
                
        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
    
    # Sort by confidence (lowest first - most urgent)
    review_items.sort(key=lambda x: x["confidence_score"])
    
    print(f"\nHuman Review Queue ({len(review_items)} items)")
    print("=" * 70)
    
    for i, item in enumerate(review_items[:args.limit], 1):
        score = item["confidence_score"]
        breakdown = item["breakdown"]
        
        print(f"\n[{i}] {item.get('file', 'unknown')}")
        print(f"    Score: {score:.3f} | Verdict: {item['verdict']}")
        print(f"    L4: {breakdown['layer_4_fact_check']:.2f} | "
              f"L5: {breakdown['layer_5_temporal']:.2f} | "
              f"L6: {breakdown['layer_6_rag']:.2f}")
        print(f"    Grounding: {breakdown['grounding_score']:.2f} | "
              f"Credibility: {breakdown['source_credibility']:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Vanta Layer 7: Confidence Scoring & Human Review")
    subparsers = parser.add_subparsers(dest="command")
    
    # Credibility scoring
    cred_parser = subparsers.add_parser("credibility", help="Score source credibility")
    cred_parser.add_argument("--urls", nargs="+", help="URLs/domains to score")
    
    # Confidence scoring
    conf_parser = subparsers.add_parser("confidence", help="Calculate confidence scores")
    conf_parser.add_argument("--input", help="Input evidence chain JSON file")
    conf_parser.add_argument("--output", help="Output results file")
    
    # Batch scoring
    batch_parser = subparsers.add_parser("batch", help="Batch score verifications")
    batch_parser.add_argument("--input-dir", help="Directory of verification JSONs")
    batch_parser.add_argument("--output", help="Output results file")
    
    # Review queue
    review_parser = subparsers.add_parser("review", help="Show human review queue")
    review_parser.add_argument("--input-dir", help="Directory of verification JSONs")
    review_parser.add_argument("--limit", type=int, default=20, help="Max items to show")
    
    args = parser.parse_args()
    
    if args.command == "credibility":
        score_credibility(args)
    elif args.command == "confidence":
        score_confidence(args)
    elif args.command == "batch":
        batch_score(args)
    elif args.command == "review":
        review_queue(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()