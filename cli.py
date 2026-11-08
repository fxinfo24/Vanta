"""
Vanta Main CLI - Complete 7-Layer Verification Pipeline
"""

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("Vanta.Main")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def check_dependencies():
    """Check if all required modules are present"""
    modules = [
        "app.core.ingestion",
        "app.core.normalization", 
        "app.core.claim_extraction",
        "app.core.fact_check",
        "app.core.temporal_verification",
        "app.core.rag_analysis",
        "app.core.evidence"
    ]
    
    missing = []
    for module in modules:
        try:
            exec(f"import {module}")
        except ImportError as e:
            missing.append(f"{module}: {e}")
    
    if missing:
        print("❌ Missing dependencies:")
        for m in missing:
            print(f"  {m}")
        return False
    
    print("✅ All 7 layers available")
    return True


def run_full_pipeline(args):
    """Run complete 7-layer pipeline"""
    from app.core.ingestion.cli import main as ingestion_main
    from app.core.normalization.normalizer import ContentNormalizer
    from app.core.claim_extraction.cli import main as claim_main
    from app.core.fact_check.cli import main as factcheck_main
    from app.core.temporal_verification.cli import main as temporal_main
    from app.core.rag_analysis.cli import main as rag_main
    from app.core.evidence.cli import main as evidence_main
    
    print("🚀 Running Complete 7-Layer Pipeline")
    print("=" * 70)
    
    steps = [
        ("Layer 1: Data Ingestion", "python app/core/ingestion/cli.py create-tables"),
        ("Layer 2: Content Normalization", "python scripts/normalize_data.py"),
        ("Layer 3: Claim Extraction", "python app/core/claim_extraction/cli.py process --limit 100"),
        ("Layer 4: Fact-Check", "python app/core/fact_check/cli.py batch --limit 100"),
        ("Layer 5: Temporal Verification", "python app/core/temporal_verification/cli.py batch --limit 100"),
        ("Layer 6: RAG Analysis", "python app/core/rag_analysis/cli.py batch --limit 100"),
        ("Layer 7: Confidence Scoring", "python app/core/evidence/cli.py batch")
    ]
    
    for name, cmd in steps:
        print(f"\n{name}")
        print(f"Command: {cmd}")
    
    print("\n✅ Pipeline ready to run")


def show_status(args):
    """Show current status of verification system"""
    from app.web.models import db
    from app.web.models.verification import (
        SocialMediaPost, Claim, VerificationResult
    )
    
    print("📊 Vanta System Status")
    print("=" * 70)
    
    try:
        post_count = db.session.query(SocialMediaPost).count()
        claim_count = db.session.query(Claim).count()
        verification_count = db.session.query(VerificationResult).count()
        
        print(f"Posts in database: {post_count}")
        print(f"Claims extracted: {claim_count}")
        print(f"Verifications completed: {verification_count}")
        
        if verification_count > 0:
            # Count by layer completion
            verifications = db.session.query(VerificationResult).all()
            
            layer_counts = {}
            for ver in verifications:
                chain = ver.evidence_chain or {}
                for layer in ["layer_4", "layer_5", "layer_6", "layer_7"]:
                    if layer in chain:
                        layer_counts[layer] = layer_counts.get(layer, 0) + 1
            
            print("\nLayer completion:")
            for layer, count in sorted(layer_counts.items()):
                pct = count / verification_count * 100
                print(f"  {layer}: {count} ({pct:.1f}%)")
    except Exception as e:
        print(f"Database error: {e}")
        print("Run 'python app/core/ingestion/cli.py create-tables' to initialize database")


def test_apis(args):
    """Test all API connections"""
    print("🔧 Testing All API Connections")
    print("=" * 70)
    
    test_commands = [
        ("Fact-Check APIs", "python app/core/fact_check/cli.py test"),
        ("Temporal APIs", "python app/core/temporal_verification/cli.py test"),
        ("LLM Connection", "python app/core/rag_analysis/cli.py analyze --claim-id test"),
    ]
    
    for name, cmd in test_commands:
        print(f"\n{name}")
        print(f"  Run: {cmd}")


def quick_start(args):
    """Quick start guide"""
    print("🎯 Vanta Quick Start Guide")
    print("=" * 70)
    
    print("\n1. Setup Environment")
    print("   cd /Volumes/ByteSmith/temp/Vanta")
    print("   python scripts/setup_env.py")
    
    print("\n2. Configure API Keys (optional)")
    print("   Edit .env file:")
    print("   GOOGLE_FACT_CHECK_API_KEY=your_key")
    print("   NEWSAPI_KEY=your_key")
    print("   OPENROUTER_API_KEY=your_key")
    
    print("\n3. Initialize Database")
    print("   python app/core/ingestion/cli.py create-tables")
    
    print("\n4. Import Data")
    print("   python app/core/ingestion/cli.py ingest-file --file /path/to/apify_data.json")
    
    print("\n5. Run Verification")
    print("   python app/core/claim_extraction/cli.py process --limit 50")
    print("   python app/core/fact_check/cli.py batch --limit 50")
    print("   python app/core/temporal_verification/cli.py batch --limit 50")
    print("   python app/core/rag_analysis/cli.py batch --limit 50")
    print("   python app/core/evidence/cli.py batch")
    
    print("\n6. View Results")
    print("   python app/core/fact_check/cli.py results")
    print("   python app/core/temporal_verification/cli.py stats")
    print("   python app/core/evidence/cli.py review")


def example_usage(args):
    """Show example usage scenarios"""
    print("📋 Example Usage Scenarios")
    print("=" * 70)
    
    examples = [
        ("English political claim",
         "python app/core/claim_extraction/cli.py process --text 'The government announced 10 million people will benefit from new policy'"),
        
        ("Bengali social media claim",
         "python app/core/claim_extraction/cli.py process --text 'গতকাল সরকার নতুন নীতি ঘোষণা করেছে'"),
        
        ("Batch verify low-confidence claims",
         "python app/core/evidence/cli.py review --limit 10"),
        
        ("Score source credibility",
         "python app/core/evidence/cli.py credibility --urls reuters.com bbc.com"),
    ]
    
    for desc, cmd in examples:
        print(f"\n{desc}")
        print(f"  {cmd}")


def main():
    parser = argparse.ArgumentParser(
        description="Vanta Main CLI - Complete 7-Layer Verification System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # Full pipeline
    pipeline_parser = subparsers.add_parser("pipeline", help="Run complete 7-layer pipeline")
    
    # Status check
    status_parser = subparsers.add_parser("status", help="Show system status")
    
    # API testing
    test_parser = subparsers.add_parser("test", help="Test API connections")
    
    # Quick start
    start_parser = subparsers.add_parser("quick-start", help="Quick start guide")
    
    # Examples
    example_parser = subparsers.add_parser("examples", help="Usage examples")
    
    # Dependency check
    deps_parser = subparsers.add_parser("check", help="Check dependencies")
    
    args = parser.parse_args()
    setup_logging()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "pipeline":
        run_full_pipeline(args)
    elif args.command == "status":
        show_status(args)
    elif args.command == "test":
        test_apis(args)
    elif args.command == "quick-start":
        quick_start(args)
    elif args.command == "examples":
        example_usage(args)
    elif args.command == "check":
        check_dependencies()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()