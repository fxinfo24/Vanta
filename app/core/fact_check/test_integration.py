"""
Integration test for Layer 4 fact-check system
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

from app.web.models import db
from app.web.models.verification import SocialMediaPost, Claim, VerificationResult, ClaimType, LanguageCode, Platform
from app.core.fact_check.engine import create_fact_check_engine
from app.core.fact_check.clients import GoogleFactCheckClient, MockFactCheckClient
from app.core.fact_check.matcher import FactCheckMatcher
from datetime import datetime


def setup_test_database():
    """Setup test database session"""
    # Use SQLite in-memory for testing
    from app.web.database import SessionLocal
    return SessionLocal()


def test_fact_check_matcher():
    """Test semantic similarity matcher"""
    print("Testing FactCheckMatcher...")
    
    matcher = FactCheckMatcher(similarity_threshold=0.3)
    
    # Test same language matching
    text1 = "The government announced new policies."
    text2 = "Government announces new policy changes."
    
    similarity = matcher.calculate_similarity(text1, text2, "en")
    print(f"  EN Similarity: {similarity:.2f}")
    
    # Test Bengali matching
    text_bn1 = "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।"
    text_bn2 = "সরকার নতুন নীতি ঘোষণা করছে।"
    
    similarity_bn = matcher.calculate_similarity(text_bn1, text_bn2, "bn")
    print(f"  BN Similarity: {similarity_bn:.2f}")
    
    # Test cross-language
    translated = matcher.translate_keywords(text_bn1, "bn", "en")
    print(f"  BN→EN translation: {translated}")
    
    return similarity > 0.5


def test_mock_fact_check_client():
    """Test mock fact-check client"""
    print("\nTesting MockFactCheckClient...")
    
    client = MockFactCheckClient()
    
    # Test search
    results = client.search_claim("government announced policies", language="en")
    
    print(f"  Found {len(results)} mock fact-checks")
    
    for i, result in enumerate(results[:2]):
        print(f"    Result {i+1}: {result.get('verdict')} - {result.get('claim_text')[:50]}...")
    
    return len(results) > 0


def test_fact_check_engine():
    """Test full fact-check engine"""
    print("\nTesting FactCheckEngine...")
    
    # Create test claim
    test_claim = Claim(
        id="test_claim_001",
        post_id="test_post_001",
        claim_text="10 million people will benefit from the new policy.",
        claim_hash="test_hash_001",
        claim_type=ClaimType.FACTUAL,
        claim_type_confidence=0.8,
        check_worthiness_score=0.9,
        sentence_index=0,
        entities=[{"text": "10 million", "type": "CARDINAL", "confidence": 0.95}],
        detected_language=LanguageCode.EN,
        detected_language_confidence=0.95,
        extraction_model="test",
        extracted_at=datetime.utcnow()
    )
    
    # Create engine with mock source only
    engine = create_fact_check_engine(sources=["mock"])
    
    # Test fact-check
    result = engine.fact_check_claim(test_claim)
    
    print(f"  Claim: {test_claim.claim_text[:60]}...")
    print(f"  Verdict: {result['verdict_summary']['verdict']}")
    print(f"  Confidence: {result['verdict_summary']['confidence']:.2f}")
    print(f"  Matches found: {result['matches_found']}")
    
    return result['matches_found'] > 0


def test_language_specific_matching():
    """Test language-specific fact-checking"""
    print("\nTesting language-specific matching...")
    
    matcher = FactCheckMatcher()
    
    # Test Bengali claim
    bengali_claim = "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।"
    
    mock_fact_checks = [
        {
            "claim_text": "Yesterday the government announced new policies.",
            "verdict": "True",
            "languages": ["en"],
            "source": "google"
        },
        {
            "claim_text": "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।",
            "verdict": "সত্য",
            "languages": ["bn"],
            "source": "mock_bn"
        }
    ]
    
    matches = matcher.match_to_fact_checks(
        claim_text=bengali_claim,
        claim_language="bn",
        fact_checks=mock_fact_checks
    )
    
    print(f"  Bengali claim matches: {len(matches)}")
    
    for match in matches:
        print(f"    Match: {match.get('verdict')} (similarity: {match.get('similarity_score', 0):.2f})")
    
    return len(matches) > 0


def run_all_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("Layer 4: Fact-Check Integration Tests")
    print("=" * 60)
    
    test_results = {}
    
    test_results["matcher"] = test_fact_check_matcher()
    test_results["mock_client"] = test_mock_fact_check_client()
    test_results["engine"] = test_fact_check_engine()
    test_results["language_matching"] = test_language_specific_matching()
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    return all_passed


if __name__ == "__main__":
    # Don't actually run database operations in test
    # Just test the logic
    success = run_all_tests()
    sys.exit(0 if success else 1)