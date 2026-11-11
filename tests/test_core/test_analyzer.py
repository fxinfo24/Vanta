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


def test_deep_collection_reports_completed_steps_not_elapsed_time():
    """Progress narrates work that finished: feeds read, posts commented on."""
    from app.core.deep_collector import DeepDossierCollector

    class FakeClient:
        def get_facebook_profile(self, username):
            return {"username": username, "follower_count": 100}

        def get_facebook_posts(self, username, count=30):
            return [{"id": "p1", "text": "hello there friend"}]

        def get_facebook_reels(self, username, count=20):
            return [{"id": "r1", "text": "a reel text here"}]

        def get_facebook_comments(self, post_id, count=30):
            return [{"text": "nice"}, {"text": "agreed"}]

        def get_facebook_transcript(self, post_id):
            return {"transcript": "spoken words"}

        def get_age_and_gender(self, url):
            return {"age": 30, "gender": "male"}

    events = []
    collector = DeepDossierCollector(client=FakeClient())
    collector.cross_platform_discovery = lambda *a, **k: {"discovered_accounts": {}}
    collector.deep_dossier(
        platform="facebook", username="someone",
        on_stage=lambda name, note, done, total: events.append((name, note, done, total)),
    )

    stages = [e[0] for e in events]
    assert stages[0] == "profile"
    assert "feeds" in stages and "comments" in stages and "collected" in stages
    feed_events = [e for e in events if e[0] == "feeds"]
    assert feed_events[0][3] == 2, "two facebook feeds are planned"
    assert "2 of 2 feeds" in feed_events[-1][1]
    comment_events = [e for e in events if e[0] == "comments"]
    # Two unique items survived dedupe, so two posts get comments read.
    assert comment_events[-1][2] == comment_events[-1][3] == 2
    assert "4 comments" in comment_events[-1][1]
    collected = events[-1][1]
    assert "posts" in collected and "comments" in collected


def test_analyzer_progress_never_moves_backwards(analyzer, monkeypatch):
    """Percentages follow completed stages and never regress."""
    seen = []

    class FakeCollector:
        def deep_dossier(self, platform, username, on_stage=None, **kwargs):
            on_stage("profile", "fetching the profile", None, None)
            on_stage("feeds", "read 1 of 2 feeds (5 posts so far)", 1, 2)
            on_stage("feeds", "read 2 of 2 feeds (9 posts so far)", 2, 2)
            return {
                "profile": {"username": username, "follower_count": 100},
                "content": [{"id": "p1", "text": "hello there"}],
                "comments_analysis": {"total_comments_collected": 4},
                "statistics": {},
            }

    class FakeIntel:
        def generate_full_report(self, dossier):
            return {"core_intelligence": {}, "executive_summary": "x"}

    monkeypatch.setattr(
        "app.core.deep_collector.create_deep_collector", lambda *a, **k: FakeCollector()
    )
    monkeypatch.setattr(
        "app.core.intelligence_analyzer.create_intelligence_analyzer", lambda *a, **k: FakeIntel()
    )

    analyzer.analyze_profile(
        "facebook", "someone", progress=lambda m, p: seen.append((m, p))
    )

    percents = [p for _, p in seen if p is not None]
    assert percents == sorted(percents), percents
    assert percents[0] >= 10 and percents[-1] >= 90
    # Counts in the text are the ones actually collected.
    assert any("1 posts and 4 comments" in m for m, _ in seen)


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


def test_benchmark_excludes_uncited_inauthentic_labels():
    """An 'inauthentic' label without a citation must not count as ground truth."""
    from app.core.authenticity import validate_benchmark_labels

    sources = [{"id": "twibot-20", "name": "Twibot-20"}]
    result = validate_benchmark_labels([
        {"platform": "facebook", "profile_id": "real", "is_inauthentic": False},
        {"platform": "facebook", "profile_id": "uncited", "is_inauthentic": True},
        {"platform": "facebook", "profile_id": "unknownref", "is_inauthentic": True,
         "source_ref": "made-up", "label_reason": "spam"},
        {"platform": "facebook", "profile_id": "noreason", "is_inauthentic": True,
         "source_ref": "twibot-20"},
        {"platform": "facebook", "profile_id": "cited", "is_inauthentic": True,
         "source_ref": "twibot-20", "label_reason": "automation disclosed by the operator"},
    ], sources)

    assert [r["profile_id"] for r in result["usable"]] == ["real", "cited"]
    assert len(result["rejected"]) == 3


def test_benchmark_withholds_accuracy_when_no_inauthentic_labels():
    """Only-authentic sets measure false positives, not accuracy."""
    from app.core.authenticity import evaluate_authenticity_benchmark

    labels = [{"platform": "facebook", "profile_id": pid, "is_inauthentic": False,
               "label_source": "official-organisation-account"} for pid in ("a", "b", "c")]
    scored = [{"platform": "facebook", "profile_id": p, "bot_likelihood": 0.2} for p in ("a", "b")]
    scored.append({"platform": "facebook", "profile_id": "c", "bot_likelihood": 0.9})

    report = evaluate_authenticity_benchmark(scored, labels)

    assert report["accuracy"] is None
    assert report["recall"] is None
    assert report["false_positive_rate"] == 0.333
    assert any("No inauthentic account" in w for w in report["warnings"])


def test_section_receipts_must_be_verbatim_from_collected_posts():
    """Paraphrased receipts are dropped exactly like invented ones."""
    from app.core.platform_prompts import verify_claim_evidence

    content = [{"text": "Gas, electricity and water, or I chew up politics."},
               {"text": "Load shedding again in Dhaka tonight."}]
    payload = {"temperament": {"label": "Angry"}, "evidence": [
        {"claim": "temperament=Angry", "quote": "Load shedding again in Dhaka tonight."},
        {"claim": "interests=hiking", "quote": "Goes hiking every weekend"},
    ]}

    out = verify_claim_evidence(payload, content, "the lifestyle section")

    assert out["evidence_verified"] == 1
    assert [e["claim"] for e in out["evidence"]] == ["temperament=Angry"]
    assert out["evidence_rejected"] == 1
    assert any("lifestyle" in lim for lim in out["limitations"])


def test_benchmark_csv_import_requires_citation(tmp_path):
    """An imported bot label without a resolvable source is rejected, not scored."""
    from app.core.authenticity import load_benchmark_csv

    csv_path = tmp_path / "labels.csv"
    csv_path.write_text(
        "platform,profile_id,is_inauthentic,source_ref,label_reason\n"
        "twitter,human1,FALSE,,known journalist\n"
        "twitter,bot1,TRUE,twibot-20,automation disclosed\n"
        "twitter,bot2,TRUE,,spam\n"
        "twitter,bot3,TRUE,no-such-source,spam\n"
        "twitter,bot4,MAYBE,twibot-20,unclear\n",
        encoding="utf-8",
    )

    result = load_benchmark_csv(csv_path, sources=[{"id": "twibot-20"}])

    assert [a["profile_id"] for a in result["accounts"]] == ["human1", "bot1"]
    assert len(result["rejected"]) == 3


def test_benchmark_csv_import_names_missing_columns(tmp_path):
    """A file missing the citation columns must fail loudly."""
    from app.core.authenticity import load_benchmark_csv

    csv_path = tmp_path / "labels.csv"
    csv_path.write_text("platform,profile_id\nfacebook,abc\n", encoding="utf-8")

    try:
        load_benchmark_csv(csv_path)
    except ValueError as exc:
        assert "source_ref" in str(exc)
    else:
        raise AssertionError("missing columns should raise")


def test_special_category_sections_are_off_by_default(monkeypatch):
    """Belief/relationship/substance inference must not run unless opted in."""
    monkeypatch.delenv("ALLOW_SPECIAL_CATEGORY_INFERENCE", raising=False)
    monkeypatch.setattr("app.utils.config.load_config", lambda: {"privacy": {}})

    from app.core.behavioral_analyzer import BehavioralAnalyzer
    from app.utils.config import allows_special_category_inference

    assert allows_special_category_inference() is False

    class VoluntarilyDetailed:
        prompt = ""

        def analyze(self, prompt, system_prompt=None, model_type=None):
            VoluntarilyDetailed.prompt = prompt
            return {"temperament": {"label": "Calm"},
                    "relationships": {"attachment_style": "Avoidant"},
                    "lifestyle_risks": {"drug_alcohol_indicated": True},
                    "evidence": []}

    out = BehavioralAnalyzer(VoluntarilyDetailed()).analyze_behavior({
        "username": "x", "platform": "facebook", "profile": {"username": "x"},
        "content": [{"text": "a normal post about the weather"}],
    })

    assert "lifestyle_risks" not in VoluntarilyDetailed.prompt
    assert out["relationships"]["status"] == "not_collected"
    assert out["lifestyle_risks"]["status"] == "not_collected"
    assert out["relationships"]["code"] == "special_category_not_inferred"
    assert "Avoidant" not in str(out["relationships"])
    # The payload reaches API consumers, exports and the PDF, so it must not
    # name internal config keys or policy machinery.
    for leak in ("privacy.", "allow_special_category_inference", "by policy"):
        assert leak not in str(out)


def test_layer4_confidence_is_read_from_the_chain_not_from_the_composite():
    """Layer 4 scores into the evidence chain; the column is output, not input.

    Reading `confidence_score` first meant the Layer 7 composite was fed back in
    as if it were a fact-check result, and left the component at 0.0 for every
    freshly verified claim.
    """
    from types import SimpleNamespace
    from app.core.evidence.confidence_scorer import ConfidenceScorer

    scorer = ConfidenceScorer()
    fresh = SimpleNamespace(
        evidence_chain={"layer_4": {"verdict_summary": {"confidence": 0.8}}},
        confidence_score=0.0,
    )
    assert scorer._extract_layer4_score(fresh) == 0.8

    rescored = SimpleNamespace(
        evidence_chain={"layer_4": {"verdict_summary": {"confidence": 0.8}}},
        confidence_score=0.3,  # previous composite, must be ignored
    )
    assert scorer._extract_layer4_score(rescored) == 0.8

    legacy = SimpleNamespace(evidence_chain={}, confidence_score=0.42)
    assert scorer._extract_layer4_score(legacy) == 0.42


def test_credit_balance_reads_the_field_the_api_actually_sends(monkeypatch):
    """The live balance endpoint answers `creditCount` (the docs show another name).

    Reading the documented `credits_remaining` returned None against the real
    API, so the dashboard kept showing a stale number.
    """
    import app.core.scrape_client as sc

    class Response:
        status_code = 200

        def json(self):
            return {"success": True, "creditCount": 1093,
                    "message": "You have 1093 credits remaining."}

    monkeypatch.setattr(sc.requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(sc, "record_credits", lambda remaining: None)
    monkeypatch.setenv("SCRAPECREATORS_API_KEY", "test-key")

    assert sc.fetch_credit_balance() == 1093


def test_consumer_analysis_is_skipped_without_commerce_signals():
    """A model asked to profile purchases from zero signals can only invent."""
    from app.core.consumer_intelligence import ConsumerIntelligenceAnalyzer

    class Exploding:
        def analyze(self, *args, **kwargs):
            raise AssertionError("consumer analysis must not run without signals")

    out = ConsumerIntelligenceAnalyzer(Exploding()).generate_consumer_profile({
        "username": "x", "profile": {"username": "x"},
        "content": [{"text": "the weather is nice today"}],
    })

    assert out["forecast_90_day"]["predicted_purchases"] == []
    assert out["current_usage"]["brands"] == []
    assert "No purchase, brand or product signals" in out["limitations"]


def test_gated_notice_is_safe_to_publish():
    """The gated payload is shown to users, exported and rendered in the PDF.

    Regression: it read "...disabled by policy
    (privacy.allow_special_category_inference)" - an internal config key on screen.
    """
    from app.core.behavioral_analyzer import gated_notice

    notice = gated_notice()
    assert notice["gated"] is True and notice["status"] == "not_collected"
    assert notice["code"] == "special_category_not_inferred"
    text = " ".join(str(v) for v in notice.values()).lower()
    for leak in ("privacy", "allow_special", "policy", "config", "flag"):
        assert leak not in text


def test_special_category_sections_requested_when_enabled(monkeypatch):
    """Opting in restores the sections instead of leaving a permanent hole."""
    monkeypatch.setenv("ALLOW_SPECIAL_CATEGORY_INFERENCE", "true")

    from app.core.behavioral_analyzer import BehavioralAnalyzer
    from app.utils.config import allows_special_category_inference

    assert allows_special_category_inference() is True

    class Capturing:
        prompt = ""

        def analyze(self, prompt, system_prompt=None, model_type=None):
            Capturing.prompt = prompt
            return {"relationships": {"attachment_style": "Secure"}}

    out = BehavioralAnalyzer(Capturing()).analyze_behavior({
        "username": "x", "platform": "facebook", "profile": {"username": "x"},
        "content": [{"text": "a normal post about the weather"}],
    })

    assert '"lifestyle_risks"' in Capturing.prompt
    assert out["relationships"]["attachment_style"] == "Secure"


def test_empty_completion_recovers_with_a_configured_fallback_model(monkeypatch):
    """A flaky free model must not blank a section it could have answered.

    Measured live: nemotron-3-ultra returned 200 with content=None three times
    for the same prompt, then content - so retrying the same model is not a
    retry that can help. A different model is.
    """
    from app.core.openrouter_client import openrouter_client

    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "alt/model:free,other/model:free")
    calls = []

    def fake_request(messages, model=None, temperature=0.7, max_tokens=2000):
        calls.append((model, max_tokens))
        return '{"ok": true}' if model == "alt/model:free" else ""

    monkeypatch.setattr(openrouter_client, "_make_request", fake_request)

    text = openrouter_client._complete([{"role": "user", "content": "hi"}], "primary/model",
                                       max_tokens=3000)
    assert json.loads(text) == {"ok": True}
    # Same model once at the requested budget, once with room for reasoning
    # tokens, then a different model - a blank answer after all three is absence.
    assert [m for m, _ in calls] == ["primary/model", "primary/model", "alt/model:free"]
    assert calls[1][1] == 6000 and calls[2][1] == 6000

    monkeypatch.delenv("OPENROUTER_FALLBACK_MODELS")
    assert openrouter_client._complete([{"role": "user", "content": "hi"}], "primary/model") == ""


def test_sentiment_is_scored_from_posts_not_a_default(analyzer):
    """An upbeat 41-post profile must not come back as 100% neutral."""
    dossier = {"content": [
        {"text": "Congratulations to everyone who voted today - great work!"},
        {"text": "So happy to celebrate with this amazing team."},
        {"text": "Terrible news about the storm; thinking of everyone affected."},
    ]}
    out = analyzer._sentiment_section({}, dossier)
    assert out["positive"] > 0
    assert sum(out[k] for k in ("positive", "neutral", "negative")) == 100
    assert out["overall"] in ("positive", "neutral", "negative")

    # Nothing collected: no split to report rather than a fabricated one.
    assert analyzer._sentiment_section({}, {}) == {
        "overall": "unknown", "positive": 0, "neutral": 0, "negative": 0
    }


def test_sentiment_survives_without_nltk(analyzer, monkeypatch):
    """Production installs no nltk; the offline scorer must not read all-neutral."""
    import app.utils.nlp_utils as nlp

    monkeypatch.setattr(nlp, "NLTK_AVAILABLE", False)
    long_post = ("Today we gathered with neighbors across the city to talk about the work ahead. "
                 "Thanks to everyone who showed up early, stayed late and made it a great day.")
    out = analyzer._sentiment_section({}, {"content": [{"text": long_post}]})
    assert out["positive"] == 100, out
    assert nlp.sentiment_backend() == "lexicon"


def test_missing_badge_field_is_unknown_not_false():
    """No badge in the payload means unmeasured, not "not verified"."""
    from unittest.mock import Mock

    from app.core.scrape_client import ScrapeCreatorsClient

    client = Mock()
    without_badge = ScrapeCreatorsClient._normalize_generic_data(
        client, {"id": "1", "name": "Someone", "followerCount": 10}, "facebook")
    with_badge = ScrapeCreatorsClient._normalize_generic_data(
        client, {"id": "1", "name": "Someone", "verified": False}, "facebook")

    assert without_badge["verified"] is None
    assert with_badge["verified"] is False


def test_unknown_verification_is_not_reported_as_unverified():
    """The scoring path must not add "Account not verified" out of nothing."""
    from app.core.authenticity import ProfileAuthenticityAnalyzer

    analyzer = ProfileAuthenticityAnalyzer()
    profile = {"followers_count": 1000, "bio": "hello", "posts_count": 5}

    unknown = analyzer.analyze_authenticity(profile, {"key_insights": ["a"]})
    refused = analyzer.analyze_authenticity({**profile, "verified": False}, {"key_insights": ["a"]})

    assert "Account not verified" not in unknown["flags"]
    assert "Account not verified" in refused["flags"]
    assert unknown["components"]["verification"] is None


def test_truncated_json_moves_on_to_the_fallback_model(monkeypatch):
    """A section cut mid-JSON must not cost the section when another model can answer."""
    from app.core.openrouter_client import openrouter_client

    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "alt/model:free")
    calls = []

    def fake_request(messages, model=None, temperature=0.7, max_tokens=2000):
        calls.append((model, max_tokens))
        if model == "alt/model:free":
            return '{"themes": ["civic"], "ok": true}'
        return '{"themes": ["civic"'   # cut off mid-JSON

    monkeypatch.setattr(openrouter_client, "_make_request", fake_request)
    out = openrouter_client._request_json(
        [{"role": "user", "content": "hi"}], "primary/model", 0.3, 3000, label="test")
    assert out["themes"] == ["civic"]
    assert calls[-1] == ("alt/model:free", 3000)


def test_private_facebook_profile_is_reported_not_collected():
    """A private profile is a 200 with no body, so the status has to travel.

    ScrapeCreators answers an inaccessible profile with `success: true`,
    `isPrivate: true` and zero credits. Nothing raises, every feed returns the
    same empty payload, and the run used to finish with an analysis of nothing.
    """
    from unittest.mock import Mock

    from app.core.scrape_client import ScrapeCreatorsClient
    from app.core.deep_collector import DeepDossierCollector
    from app.core.analyzer import SocialMediaAnalyzer, CollectionEmptyError

    raw = {"success": True, "credits_charged": 0, "isPrivate": True,
           "account_status": "private", "message": "Profile is private",
           "url": "https://www.facebook.com/someone"}

    client = Mock()
    client.get_facebook_profile.side_effect = lambda username: \
        ScrapeCreatorsClient._normalize_generic_data(client, raw, "facebook")

    collector = DeepDossierCollector(client=client)
    dossier = collector.deep_dossier("facebook", "someone")

    assert dossier["unavailable"]["reason"] == "private"
    assert "Profile is private" in dossier["unavailable"]["message"]
    assert dossier["content"] == []
    # Feeds cannot answer for a private profile; asking only spends calls.
    client.get_facebook_posts.assert_not_called()

    quick = collector.quick_scan("facebook", "someone")
    assert quick["unavailable"]["reason"] == "private"

    with pytest.raises(CollectionEmptyError) as excinfo:
        SocialMediaAnalyzer._require_something_to_analyse("facebook", "someone", dossier)
    assert "private" in str(excinfo.value)


def test_analyzer_refuses_to_report_on_an_empty_dossier(analyzer, monkeypatch):
    """No model pass may run on a dossier with no subject.

    The old behaviour produced a COMPLETED task whose summary said generation
    failed and whose every section was 'not measured' - indistinguishable from
    findings about the account.
    """
    from app.core.analyzer import CollectionEmptyError

    class FakeCollector:
        def deep_dossier(self, platform, username, on_stage=None, **kwargs):
            return {
                "profile": None,
                "content": [],
                "errors": ["the provider reports this profile as private (Profile is private)"],
                "unavailable": {"reason": "private",
                                "message": "the provider reports this profile as private "
                                           "(Profile is private)"},
                "statistics": {},
            }

    ran = {"model": False}

    class FakeIntel:
        def generate_full_report(self, dossier):
            ran["model"] = True
            return {}

    monkeypatch.setattr("app.core.deep_collector.create_deep_collector",
                        lambda *a, **k: FakeCollector())
    monkeypatch.setattr("app.core.intelligence_analyzer.create_intelligence_analyzer",
                        lambda *a, **k: FakeIntel())

    with pytest.raises(CollectionEmptyError) as excinfo:
        analyzer.analyze_profile("facebook", "someone")

    assert "private" in str(excinfo.value)
    assert "No report was generated" in str(excinfo.value)
    assert ran["model"] is False, "an empty dossier must not reach the model"


def test_quick_scan_posts_are_readable_by_every_analyzer():
    """A quick scan must publish its posts under `content`.

    Regression: quick_scan wrote `recent_content`, which no analyzer reads, so a
    quick run with real posts was analysed and reported as zero posts.
    """
    from app.core.deep_collector import DeepDossierCollector
    from app.core.analyzer import SocialMediaAnalyzer

    posts = [{"text": "a real collected post", "likes": 3}]
    client = Mock()
    client.get_facebook_profile.return_value = {"username": "someone", "follower_count": 5}
    client.get_facebook_posts.return_value = posts

    dossier = DeepDossierCollector(client=client).quick_scan("facebook", "someone")

    assert dossier["content"] == posts
    assert "recent_content" not in dossier

    coverage = SocialMediaAnalyzer._build_coverage({}, dossier)
    assert coverage["counts"]["posts"] == 1
    assert {i["section"] for i in coverage["measured"]} >= {"sentiment", "content"}


def test_second_run_reuses_the_cached_dossier_instead_of_scraping(app, monkeypatch):
    """Re-analysis must not spend credits on data it already has.

    The cache is what makes regeneration and repeated analysis free: the first
    run collects (and pays), the second reads the stored dossier.
    """
    from app.core.analyzer import SocialMediaAnalyzer
    from app.web.models.dossier import store_cached_dossier, DossierCache
    from app.web.models import db
    from app.utils.config import set_user_context, reset_user_context

    dossier = {
        "collection_mode": "deep",
        "platform": "facebook",
        "username": "cached_subject",
        "collected_at": "2026-11-01T10:00:00",
        "profile": {"username": "cached_subject", "follower_count": 10},
        "content": [{"text": "a cached post"}],
        "errors": [],
    }
    with app.app_context():
        # Cache rows are scoped by owner id; no FK is enforced, so a literal id
        # keeps this test independent of the auth fixtures.
        user_id = 42
        store_cached_dossier(db.session, user_id, "facebook", "cached_subject", dossier, ttl_hours=12)
        assert db.session.query(DossierCache).count() == 1

        token = set_user_context({"user_id": user_id, "keys": {}, "preferred_model": None,
                                  "default_mode": "deep"})
        try:
            analyzer = SocialMediaAnalyzer()
            cached = analyzer._cache_lookup("facebook", "cached_subject")
            assert cached is not None
            assert cached["content"] == [{"text": "a cached post"}]

            # Expiry is what forces a new collection.
            from datetime import datetime, timedelta
            from app.web.models.dossier import get_cached_dossier
            assert get_cached_dossier(db.session, user_id, "facebook", "cached_subject",
                                      now=datetime.utcnow() + timedelta(hours=13)) is None
        finally:
            reset_user_context(token)


def test_cli_and_desktop_runs_use_an_operator_local_cache(monkeypatch):
    """A run with no signed-in user still reuses its own collected dossier.

    CLI and desktop runs execute without an app context or user id; before this
    they collected every time, so re-running the same handle on the desktop paid
    again for data the local database already held. No `app` fixture here on
    purpose: an app context is exactly what this path does not have.
    """
    from flask import has_app_context
    from app.web.app import create_app
    import app.core.analyzer as analyzer_module
    from app.core.analyzer import SocialMediaAnalyzer
    from app.web.models import db
    from app.web.models.dossier import (
        DossierCache, LOCAL_CACHE_OWNER, get_cached_dossier,
    )

    local_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "PROVIDER_USAGE_PATH": "/nonexistent/vanta_provider_usage.json",
    })
    with local_app.app_context():
        db.create_all()

    monkeypatch.setattr(analyzer_module, "_shared_cache_app", lambda: local_app)
    assert not has_app_context()

    analyzer = SocialMediaAnalyzer()
    stored = {"profile": {"username": "local_subject"}, "content": [{"text": "collected"}],
              "collected_at": "2026-11-09T10:00:00"}
    analyzer._cache_store("facebook", "local_subject", stored)

    with local_app.app_context():
        row = db.session.query(DossierCache).filter_by(profile_id="local_subject").one()
        assert row.user_id == LOCAL_CACHE_OWNER
        # An operator-local entry is not visible to a signed-in web user.
        assert get_cached_dossier(db.session, 7, "facebook", "local_subject") is None

    assert analyzer._cache_lookup("facebook", "local_subject")["content"] == [{"text": "collected"}]


def test_exhausted_credits_are_recorded_so_the_next_run_is_blocked(app):
    """A 402 must leave a zero balance behind, not just an error message."""
    from app.core.scrape_client import record_credits, read_credits
    from app.web.models.dossier import purge_expired_cache  # noqa: F401 (import check)

    with app.app_context():
        record_credits(0)
        observed = read_credits("/nonexistent/usage.json")
        assert observed is not None
        assert observed["credits_remaining"] == 0


def test_coverage_reports_collection_failures():
    """An empty run must say why it is empty, not just show missing sections."""
    from app.core.analyzer import SocialMediaAnalyzer

    coverage = SocialMediaAnalyzer._build_coverage({}, {
        "profile": None,
        "content": [],
        "errors": ["Profile error: CREDITS_EXHAUSTED: 402"],
    })

    assert coverage["measured"] == []
    assert coverage["collection_errors"] == ["Profile error: CREDITS_EXHAUSTED: 402"]


@patch("app.core.intelligence_analyzer.create_intelligence_analyzer")
@patch("app.core.deep_collector.create_deep_collector")
def test_progress_reports_counted_stages_not_a_timer(mock_deep_factory, mock_intel_factory, analyzer):
    """Six minutes of silence at 10% was indistinguishable from a hung run.

    Progress must come from steps the collector actually finished - feeds
    fetched, posts read - so the percentage is a count, never a clock.
    """
    mock_collector = Mock()

    def deep_dossier(**kwargs):
        on_stage = kwargs["on_stage"]
        on_stage("profile", "fetching the profile for test_user", None, None)
        on_stage("feeds", "profile collected; reading 2 feeds", 0, 2)
        on_stage("feeds", "collected posts (46 items)", 1, 2)
        on_stage("feeds", "collected reels (12 items)", 2, 2)
        on_stage("comments", "reading comments on 3 posts", 1, 3)
        on_stage("collected", "collected 50 posts and 71 comments in 240s", 1, 1)
        return {"profile": {"username": "test_user", "follower_count": 100},
                "content": [{"text": "post"}] * 50,
                "comments_analysis": {"total_comments_collected": 71},
                "statistics": {}, "connected_accounts": [], "errors": []}

    mock_collector.deep_dossier.side_effect = deep_dossier
    mock_deep_factory.return_value = mock_collector
    mock_intel = Mock()
    mock_intel.generate_full_report.return_value = {
        "core_intelligence": {"general_analysis": {}, "authenticity": {}, "predictions": {}},
        "belief_system": {}, "consumer_profile": {}, "executive_summary": "",
    }
    mock_intel_factory.return_value = mock_intel

    seen = []
    analyzer.analyze_profile("facebook", "test_user", progress=lambda m, p: seen.append((m, p)))

    messages = [m for m, _ in seen]
    percents = [p for _, p in seen if p is not None]
    assert "collected posts (46 items)" in messages
    assert any("71 comments" in m for m in messages)
    assert percents == sorted(percents), "the bar must not move backwards"
    assert percents[0] < 48 <= percents[-1], "collection work must move the bar"
    assert seen[-1][1] == 92 or seen[-1][0].startswith("report written")


@patch("app.core.intelligence_analyzer.create_intelligence_analyzer")
@patch("app.core.deep_collector.create_deep_collector")
def test_a_failing_progress_callback_cannot_break_a_paid_run(mock_deep_factory, mock_intel_factory, analyzer):
    """Reporters are best-effort: a UI problem must not lose collected data."""
    mock_deep_factory.return_value = Mock(deep_dossier=Mock(return_value={
        "profile": {"username": "test_user", "follower_count": 1},
        "content": [], "comments_analysis": {}, "statistics": {},
        "connected_accounts": [], "errors": [],
    }))
    mock_intel_factory.return_value = Mock(generate_full_report=Mock(return_value={
        "core_intelligence": {"general_analysis": {}, "authenticity": {}, "predictions": {}},
        "belief_system": {}, "consumer_profile": {}, "executive_summary": "",
    }))

    def explode(message, percent):
        raise RuntimeError("status writer is down")

    results = analyzer.analyze_profile("facebook", "test_user", progress=explode)
    assert results["metadata"]["platform"] == "facebook"
