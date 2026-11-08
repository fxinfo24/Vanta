"""
Integration tests for Vanta
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, Mock
import tempfile
import shutil

from app.core.analyzer import SocialMediaAnalyzer
from app.core.data_collector import DataCollector


@pytest.fixture
def mock_profile_data():
    """Create sample profile data for testing"""
    return {
        "profile": {
            "username": "test_user",
            "name": "Test User",
            "bio": "Software engineer passionate about technology, AI, and innovation. Love to travel and explore new cultures.",
            "join_date": "2020-01-01",
            "verification": False,
            "followers_count": 500,
            "following_count": 250,
        },
        "posts": [
            {
                "id": "post1",
                "content": "Just finished implementing a new ML model for our product. Exciting results! #machinelearning #python",
                "created_at": "2023-01-15T14:30:00Z",
                "likes": 45,
                "retweets": 12,
                "replies": 5,
            },
            {
                "id": "post2",
                "content": "Exploring Tokyo this week! Amazing city with incredible food and culture. #travel #japan",
                "created_at": "2023-02-10T08:15:00Z",
                "likes": 78,
                "retweets": 8,
                "replies": 14,
            },
            {
                "id": "post3",
                "content": "Check out this article on the future of AI in healthcare: https://example.com/article",
                "created_at": "2023-02-25T18:45:00Z",
                "likes": 32,
                "retweets": 9,
                "replies": 3,
            },
        ],
        "media": [
            {
                "id": "media1",
                "type": "image",
                "url": "https://example.com/image1.jpg",
                "caption": "Beautiful sunset in Tokyo. #travel #japan",
                "date": "2023-02-10",
            },
            {
                "id": "media2",
                "type": "video",
                "url": "https://example.com/video1.mp4",
                "caption": "Demo of our new ML model in action",
                "date": "2023-01-16",
            },
        ],
    }


@pytest.fixture
def test_config():
    """Create test configuration"""
    return {
        "rate_limits": {"twitter": 100, "facebook": 100},
        "analysis": {
            "nlp_model": "default",
            "sentiment_analysis": True,
            "confidence_threshold": 0.65,
        },
        "output": {"save_raw_data": False, "export_format": "json"},
        "logging": {"level": "INFO", "file": "test_log.log"},
    }


@patch("app.core.intelligence_analyzer.create_intelligence_analyzer")
@patch("app.core.deep_collector.create_deep_collector")
def test_full_analysis_flow(mock_deep_factory, mock_intel_factory, mock_profile_data, test_config, tmp_path):
    """Test the complete analysis flow.

    Root cause of the old failure: analyze_profile collects via
    DeepDossierCollector (create_deep_collector), not DataCollector, so the
    old patch never intercepted and real network calls ran. Both real
    factories are mocked so the test is hermetic (no credits burned).
    """
    mock_collector = Mock()
    mock_collector.deep_dossier.return_value = mock_profile_data
    mock_deep_factory.return_value = mock_collector

    mock_intel = Mock()
    mock_intel.generate_full_report.return_value = {
        "core_intelligence": {
            "general_analysis": {
                "sentiment": {"overall": "neutral"},
                "personality_traits": {}, "interests": [],
                "writing_style": {}, "content_topics": [],
            },
            "authenticity": {"overall_score": 0.9},
            "predictions": {"disclaimer": "Predictions are estimates, not guarantees."},
        },
        "belief_system": {}, "consumer_profile": {}, "executive_summary": "test",
    }
    mock_intel_factory.return_value = mock_intel

    # Create a temporary config file
    config_path = tmp_path / "test_config.json"
    with open(config_path, "w") as f:
        json.dump(test_config, f)

    # Initialize the analyzer with our test config
    analyzer = SocialMediaAnalyzer(str(config_path))

    # Run the analysis
    results = analyzer.analyze_profile("twitter", "test_user")

    # Basic validation of results
    assert "metadata" in results
    assert results["metadata"]["profile_id"] == "test_user"
    assert results["metadata"]["platform"] == "twitter"

    # Check that all analysis sections are present (current schema keys)
    assert "content_analysis" in results
    assert "authenticity" in results
    assert "predictions" in results

    # Verify content analysis has all expected sections
    content = results["content_analysis"]
    assert "personality_traits" in content
    assert "interests" in content
    assert "writing_style" in content
    assert "content_topics" in content

    # Verify authenticity analysis format
    auth = results["authenticity"]
    assert isinstance(auth.get("overall_score", 0), (int, float))

    # Verify predictions are included
    assert "disclaimer" in results["predictions"]

    # Export functionality test
    output_path = tmp_path / "test_results.json"
    analyzer.export_results(results, str(output_path))

    assert output_path.exists()

    # Verify exported file is valid JSON and contains expected data
    with open(output_path, "r") as f:
        exported_data = json.load(f)

    assert exported_data["metadata"]["profile_id"] == "test_user"
    assert "content_analysis" in exported_data
