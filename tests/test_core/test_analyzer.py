"""
Tests for the Vanta core analyzer
"""

import json
import pytest
from unittest.mock import patch, Mock, MagicMock

from app.core.analyzer import SocialMediaAnalyzer


@pytest.fixture
def test_config():
    """Create test configuration"""
    return {
        "rate_limits": {"twitter": 50, "facebook": 50},
        "analysis": {
            "nlp_model": "test_model",
            "sentiment_analysis": True,
            "confidence_threshold": 0.5,
        },
        "output": {"save_raw_data": True, "export_format": "json"},
        "logging": {"level": "DEBUG", "file": "test_analyzer.log"},
    }


@pytest.fixture
def analyzer(tmp_path, test_config):
    """Create analyzer instance with test configuration"""
    config_file = tmp_path / "test_config.json"
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    return SocialMediaAnalyzer(str(config_file))


def test_analyzer_initialization(analyzer):
    """Test analyzer initialization with config"""
    # Analyzer initializes components lazily or in __init__
    assert analyzer.content_analyzer is not None
    assert analyzer.authenticity_analyzer is not None
    assert analyzer.prediction_engine is not None
    assert hasattr(analyzer, "_get_collector")


@patch("app.core.intelligence_analyzer.create_intelligence_analyzer")
@patch("app.core.deep_collector.create_deep_collector")
def test_analyze_profile(mock_deep_factory, mock_intel_factory, analyzer):
    """Test complete profile analysis.

    NOTE (root cause of the old failure): SocialMediaAnalyzer.analyze_profile
    no longer uses DataCollector - it collects via DeepDossierCollector
    (create_deep_collector) and analyses via the intelligence engine.
    The old test patched DataCollector, so the real deep collector ran and
    burned live ScrapeCreators credits. Both real factories are mocked here
    so this test never touches the network.
    """
    mock_collector = Mock()
    mock_collector.deep_dossier.return_value = {
        "profile": {
            "username": "test_user", "display_name": "Test User", "bio": "Test bio",
            "follower_count": 100, "following_count": 50, "posts_count": 10,
            "verified": False, "location": "", "website": "",
            "profile_image_url": "", "category": "", "like_count": 0,
            "talking_about_count": 0,
        },
        "connected_accounts": [],
        "statistics": {},
    }
    mock_deep_factory.return_value = mock_collector

    mock_intel = Mock()
    mock_intel.generate_full_report.return_value = {
        "core_intelligence": {
            "general_analysis": {"sentiment": {"overall": "neutral"}},
            "authenticity": {"overall_score": 0.9},
            "predictions": {"disclaimer": "test"},
        },
        "belief_system": {}, "consumer_profile": {}, "executive_summary": "test",
    }
    mock_intel_factory.return_value = mock_intel

    results = analyzer.analyze_profile("twitter", "test_user")

    # Deep collector must be used (not the legacy DataCollector path)
    mock_deep_factory.assert_called_once()
    mock_collector.deep_dossier.assert_called_once()
    assert mock_collector.deep_dossier.call_args.kwargs["platform"] == "twitter"
    assert mock_collector.deep_dossier.call_args.kwargs["username"] == "test_user"

    # Check all required components are present (current result schema)
    assert "metadata" in results
    assert "content_analysis" in results
    assert "authenticity" in results
    assert "predictions" in results
    assert "profile_info" in results

    # Check metadata
    assert results["metadata"]["profile_id"] == "test_user"
    assert results["metadata"]["platform"] == "twitter"
    assert "analysis_date" in results["metadata"]
    assert "analyzer_version" in results["metadata"]


def test_export_results(analyzer, tmp_path):
    """Test results export functionality"""
    results = {
        "metadata": {
            "profile_id": "test_user",
            "platform": "twitter",
        },
        "test_data": "test_value",
    }

    output_file = tmp_path / "test_results.json"
    analyzer.export_results(results, str(output_file))

    # Verify file was created and contains correct data
    assert output_file.exists()
    with open(output_file) as f:
        loaded_results = json.load(f)

    assert loaded_results == results


def test_export_unsupported_format(analyzer, tmp_path):
    """Test error handling for unsupported export formats"""
    analyzer.config["output"]["export_format"] = "unsupported"

    with pytest.raises(ValueError) as exc_info:
        analyzer.export_results({}, str(tmp_path / "test.txt"))

    assert "Unsupported export format" in str(exc_info.value)


def test_benchmark_reports_insufficient_sample_instead_of_accuracy():
    """A tiny labelled set must not produce a quotable accuracy figure."""
    from app.core.authenticity import evaluate_authenticity_benchmark

    labels = [
        {"platform": "facebook", "profile_id": "a", "is_inauthentic": False,
         "label_source": "official-organisation-account"},
        {"platform": "facebook", "profile_id": "b", "is_inauthentic": True,
         "label_source": "platform-takedown-notice"},
    ]
    scored = [
        {"platform": "facebook", "profile_id": "a", "bot_likelihood": 0.1},
        {"platform": "facebook", "profile_id": "b", "bot_likelihood": 0.8},
    ]

    report = evaluate_authenticity_benchmark(scored, labels)

    assert report["n"] == 2
    assert report["usable"] is False
    assert report["confusion"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 1}
    assert any("below 20" in w for w in report["warnings"])


def test_benchmark_handles_unlabelled_and_missing_scores():
    """Accounts without a label or without a score are skipped, not counted."""
    from app.core.authenticity import evaluate_authenticity_benchmark

    report = evaluate_authenticity_benchmark(
        [{"platform": "facebook", "profile_id": "unknown", "bot_likelihood": 0.4},
         {"platform": "facebook", "profile_id": "noscore", "bot_likelihood": None}],
        [{"platform": "facebook", "profile_id": "noscore", "is_inauthentic": False,
          "label_source": "official-organisation-account"}],
    )

    assert report["n"] == 0
    assert report["usable"] is False
    assert report["rows"] == []
