"""
Vanta: RAG Analysis CLI (Layer 6)
Command line interface for AI-assisted claim analysis
"""

import argparse
import logging
import os
import sys

from app.utils.config import DEFAULT_OPENROUTER_MODEL
from app.web.models import db
from app.web.models.verification import Claim
from .rag_engine import create_rag_engine

logger = logging.getLogger("Vanta.RAG.CLI")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def analyze_single_claim(args):
    """Analyze a single claim with RAG"""
    print(f"RAG analyzing claim: {args.claim_id}")
    
    claim = db.session.query(Claim).filter_by(id=args.claim_id).first()
    
    if not claim:
        print(f"❌ Claim not found: {args.claim_id}")
        return
    
    engine = create_rag_engine(
        provider=args.provider,
        model=args.model,
        temperature=args.temperature
    )
    
    result = engine.analyze_claim(claim)
    
    print(f"\n✅ RAG Analysis complete:")
    print(f"  Verdict: {result['verdict']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Grounding: {result['grounding_score']:.2f}")
    print(f"  Evidence pieces: {result['evidence_count']}")
    print(f"  Model: {result.get('model_used', 'N/A')}")
    
    if result.get('reasoning'):
        print(f"\n  Reasoning:")
        reasoning = result['reasoning'][:500]
        for line in reasoning.split('. '):
            print(f"    • {line.strip()}")
    
    if result.get('citations'):
        print(f"\n  Citations ({len(result['citations'])}):")
        for cite in result['citations'][:5]:
            print(f"    [{cite.get('evidence_id', '?')}] {cite.get('relevant_text', '')[:60]}...")


def batch_analyze(args):
    """Batch analyze claims"""
    print(f"Batch RAG analyzing up to {args.limit} claims...")
    
    engine = create_rag_engine(
        provider=args.provider,
        model=args.model
    )
    
    results = engine.process_claims(args.limit)
    
    print(f"\n✅ Batch RAG analysis complete:")
    print(f"  Processed: {results['processed']}")
    print(f"  Successful: {results['successful']}")
    print(f"  Failed: {results['failed']}")


def view_rag_stats(args):
    """View RAG analysis statistics"""
    from app.web.models.verification import VerificationResult
    
    verifications = db.session.query(VerificationResult).all()
    
    total = len(verifications)
    with_layer6 = 0
    verdicts = {}
    avg_grounding = []
    
    for ver in verifications:
        if ver.evidence_chain and "layer_6" in ver.evidence_chain:
            with_layer6 += 1
            layer6 = ver.evidence_chain["layer_6"]
            
            verdict = layer6.get("verdict", "UNKNOWN")
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
            
            grounding = layer6.get("grounding_score", 0.0)
            avg_grounding.append(grounding)
    
    print("📊 RAG Analysis Statistics (Layer 6)")
    print("=" * 60)
    print(f"Total verifications: {total}")
    print(f"With RAG analysis: {with_layer6} ({with_layer6/total*100:.1f}%)" if total > 0 else "With RAG analysis: 0")
    
    if verdicts:
        print(f"\nVerdict distribution:")
        for verdict, count in sorted(verdicts.items()):
            pct = count / with_layer6 * 100
            print(f"  {verdict}: {count} ({pct:.1f}%)")
    
    if avg_grounding:
        avg_g = sum(avg_grounding) / len(avg_grounding)
        print(f"\nAverage grounding score: {avg_g:.3f}")
        high_ground = sum(1 for g in avg_grounding if g >= 0.7)
        print(f"Highly grounded (≥0.7): {high_ground}/{len(avg_grounding)} ({high_ground/len(avg_grounding)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Vanta RAG Analysis CLI (Layer 6)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    analyze_parser = subparsers.add_parser("analyze", help="Analyze single claim")
    analyze_parser.add_argument("claim_id", help="Claim ID to analyze")
    analyze_parser.add_argument("--provider", default="openrouter", help="LLM provider")
    analyze_parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL, help="LLM model")
    analyze_parser.add_argument("--temperature", type=float, default=0.1, help="Temperature")
    
    batch_parser = subparsers.add_parser("batch", help="Batch analyze claims")
    batch_parser.add_argument("--limit", type=int, default=50, help="Max claims to process")
    batch_parser.add_argument("--provider", default="openrouter", help="LLM provider")
    batch_parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL, help="LLM model")
    
    stats_parser = subparsers.add_parser("stats", help="View RAG statistics")
    
    args = parser.parse_args()
    setup_logging()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "analyze":
        analyze_single_claim(args)
    elif args.command == "batch":
        batch_analyze(args)
    elif args.command == "stats":
        view_rag_stats(args)


if __name__ == "__main__":
    main()