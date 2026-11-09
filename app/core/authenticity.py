"""
Vanta: Profile Authenticity Analyzer
Evaluates profile authenticity based on various signals
"""

from typing import Dict, Any, List, Tuple
import re
from datetime import datetime
import logging


class ProfileAuthenticityAnalyzer:
    """Analyzes social media profiles for authenticity signals"""

    def __init__(self):
        """Initialize the authenticity analyzer"""
        self.logger = logging.getLogger("Vanta.AuthenticityAnalyzer")

    def analyze_authenticity(
        self, profile_data: Dict[str, Any], content_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze a profile for signs of authenticity or inauthenticity

        Args:
            profile_data: Dictionary containing profile data
            content_analysis: Results from content analysis

        Returns:
            Dictionary with authenticity analysis results
        """
        self.logger.info("Analyzing profile authenticity")

        # Check if we're using mock data
        is_mock = profile_data.get("metadata", {}).get("is_mock_data", False)

        if is_mock:
            # For mock data, generate complete authenticity analysis
            return self._generate_mock_authenticity_analysis(
                profile_data, content_analysis
            )

        # For real data analysis, run the actual checks
        # Run various checks
        consistency_score = self._check_consistency(profile_data, content_analysis)
        activity_score = self._check_activity_patterns(profile_data)
        verification_status = self._check_verification(profile_data)
        account_age_score = self._check_account_age(profile_data)
        language_score = self._check_language_patterns(profile_data)

        # Calculate overall authenticity score
        # Weights could be adjusted based on importance of each factor
        weights = {
            "consistency": 0.25,
            "activity": 0.20,
            "verification": 0.15,
            "account_age": 0.20,
            "language": 0.20,
        }

        verification_value = 1.0 if verification_status else 0.5

        overall_score = (
            weights["consistency"] * consistency_score
            + weights["activity"] * activity_score
            + weights["verification"] * verification_value
            + weights["account_age"] * account_age_score
            + weights["language"] * language_score
        )

        # Generate confidence level and flags
        confidence_level, flags = self._generate_confidence_assessment(
            overall_score,
            consistency_score,
            activity_score,
            verification_status,
            account_age_score,
            language_score,
        )

        return {
            "overall_score": round(overall_score, 2),
            "confidence_level": confidence_level,
            "flags": flags,
            "components": {
                "consistency": round(consistency_score, 2),
                "activity_patterns": round(activity_score, 2),
                "verification": verification_status,
                "account_age": round(account_age_score, 2),
                "language_patterns": round(language_score, 2),
            },
        }

    def _generate_mock_authenticity_analysis(
        self, profile_data: Dict[str, Any], content_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive mock authenticity analysis for demonstration

        Args:
            profile_data: Dictionary containing profile data
            content_analysis: Results from content analysis

        Returns:
            Complete mock authenticity analysis
        """
        # Generate random but realistic-looking values
        import random

        # Use username as seed for deterministic results
        username = profile_data.get("profile", {}).get("username", "default")
        seed_value = sum(ord(c) for c in str(username))
        random.seed(seed_value)

        # Overall authenticity score - generate between 0.7 and 0.95 for demo
        overall_authenticity = {
            "score": round(random.uniform(0.7, 0.95), 2),
            "confidence": round(random.uniform(0.8, 0.95), 2),
        }

        # Decide if there are any potential issues
        potential_issues = []
        if random.random() < 0.3:  # 30% chance to have issues
            issues = [
                "Some posting patterns show minor inconsistencies",
                "Account shows occasional automated activity",
                "Writing style varies slightly between posts",
            ]
            potential_issues = random.sample(issues, random.randint(0, 2))

        # Bot likelihood analysis
        bot_likelihood = {
            "score": round(random.uniform(0.05, 0.25), 2),
            "confidence": round(random.uniform(0.7, 0.9), 2),
            "indicators": {
                "posting_pattern_regularity": round(random.uniform(0.1, 0.3), 2),
                "content_variability": round(random.uniform(0.05, 0.2), 2),
                "interaction_patterns": round(random.uniform(0.1, 0.3), 2),
                "language_markers": round(random.uniform(0.05, 0.25), 2),
            },
        }

        # Consistency score
        consistency_score = round(random.uniform(0.7, 0.9), 2)

        # Activity patterns
        posting_times = {
            "distribution": {
                "morning": round(random.uniform(0.1, 0.3), 2),
                "afternoon": round(random.uniform(0.3, 0.5), 2),
                "evening": round(random.uniform(0.2, 0.4), 2),
                "night": round(random.uniform(0.05, 0.2), 2),
            },
            "consistency": round(random.uniform(0.7, 0.9), 2),
        }

        irregular_patterns = random.random() < 0.2  # 20% chance for irregularities

        activity_patterns = {
            "posting_times": posting_times,
            "irregular_patterns": irregular_patterns,
        }

        # Maybe add some burst activities
        if random.random() < 0.3:  # 30% chance to have bursts
            burst_dates = ["2024-11-15 to 2024-11-17", "2025-01-22 to 2025-01-23"]
            activity_patterns["burst_activities"] = burst_dates

        # Maybe add some dormant periods
        if random.random() < 0.25:  # 25% chance to have dormant periods
            dormant_dates = ["2024-09-05 to 2024-10-12", "2025-02-10 to 2025-02-28"]
            activity_patterns["dormant_periods"] = dormant_dates

        # Style comparison
        style_comparison = {
            "highest_match": {
                "reference_profile": "typical_"
                + profile_data.get("metadata", {}).get("platform", "social")
                + "_user",
                "similarity_score": round(random.uniform(0.7, 0.9), 2),
                "confidence": round(random.uniform(0.7, 0.85), 2),
                "matching_features": random.sample(
                    [
                        "sentence structure",
                        "vocabulary usage",
                        "emoji patterns",
                        "punctuation style",
                    ],
                    random.randint(2, 4),
                ),
            },
            "matches": [
                {
                    "reference_profile": "typical_"
                    + profile_data.get("metadata", {}).get("platform", "social")
                    + "_user",
                    "similarity_score": round(random.uniform(0.7, 0.9), 2),
                    "confidence": round(random.uniform(0.7, 0.85), 2),
                },
                {
                    "reference_profile": "average_personal_account",
                    "similarity_score": round(random.uniform(0.5, 0.7), 2),
                    "confidence": round(random.uniform(0.6, 0.8), 2),
                },
                {
                    "reference_profile": "commercial_account",
                    "similarity_score": round(random.uniform(0.2, 0.4), 2),
                    "confidence": round(random.uniform(0.7, 0.9), 2),
                },
            ],
        }

        # Assemble complete authenticity analysis
        return {
            "overall_authenticity": overall_authenticity,
            "potential_issues": potential_issues,
            "consistency_score": consistency_score,
            "bot_likelihood": bot_likelihood,
            "activity_patterns": activity_patterns,
            "style_comparison": style_comparison,
        }

    def _check_consistency(
        self, profile_data: Dict[str, Any], content_analysis: Dict[str, Any]
    ) -> float:
        """
        Check consistency between profile elements and posting behavior

        Returns:
            Score from 0.0 (inconsistent) to 1.0 (highly consistent)
        """
        consistency_score = 0.7  # Start with average score

        # Check if writing style is consistent
        if "writing_style" in content_analysis:
            writing_style = content_analysis["writing_style"]

            # Large variations in sentence length can indicate multiple authors
            if writing_style.get("avg_sentence_length", 0) > 30:
                consistency_score -= 0.1

        # Check if posting patterns are erratic
        if "posting_patterns" in content_analysis:
            patterns = content_analysis["posting_patterns"]

            # Very high posting frequency might be suspicious
            if patterns.get("frequency", {}).get("daily_average", 0) > 20:
                consistency_score -= 0.15

        # Check topic consistency
        if "content_topics" in content_analysis:
            topics = content_analysis["content_topics"]
            # If there's a very wide spread of topics, might be suspicious
            if len(topics.get("top_topics", [])) >= 3:
                topic_values = [v for _, v in topics.get("top_topics", [])]
                if len(topic_values) >= 2:
                    # If the top topic is much more common than others, more consistent
                    if topic_values[0] > 3 * topic_values[-1]:
                        consistency_score += 0.1

        return max(0.0, min(1.0, consistency_score))

    def _check_activity_patterns(self, profile_data: Dict[str, Any]) -> float:
        """
        Check for suspicious activity patterns

        Returns:
            Score from 0.0 (suspicious patterns) to 1.0 (normal patterns)
        """
        # Default to a neutral score
        activity_score = 0.7

        posts = profile_data.get("posts", [])

        # Check for posting volume
        if len(posts) < 5:
            # Very few posts is suspicious for established accounts
            activity_score -= 0.2

        # Check for posting times
        posting_times = self._extract_posting_times(posts)

        # Look for posts at regular intervals (bot-like behavior)
        if self._detect_regular_intervals(posting_times):
            activity_score -= 0.3

        # Check for very high engagement metrics
        if self._has_abnormal_engagement(posts):
            activity_score -= 0.2

        return max(0.0, min(1.0, activity_score))

    def _check_verification(self, profile_data: Dict[str, Any]) -> bool:
        """
        Check if the account is verified by the platform

        Returns:
            Boolean indicating verification status
        """
        return profile_data.get("verified", False)

    def _check_account_age(self, profile_data: Dict[str, Any]) -> float:
        """
        Check account age and assess based on age

        Returns:
            Score from 0.0 (very new account) to 1.0 (well-established account)
        """
        # Default score for accounts with unknown creation date
        if "created_at" not in profile_data:
            return 0.5

        created_str = profile_data.get("created_at", "")

        try:
            creation_date = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ")
            now = datetime.now()

            # Calculate account age in days
            account_age_days = (now - creation_date).days

            # Score based on account age
            if account_age_days < 7:
                return 0.1  # Very new accounts are suspicious
            elif account_age_days < 30:
                return 0.3  # Less than a month
            elif account_age_days < 90:
                return 0.5  # 1-3 months
            elif account_age_days < 365:
                return 0.7  # 3-12 months
            else:
                return 0.9  # Over a year

        except (ValueError, TypeError):
            # If date parsing fails, return neutral score
            return 0.5

    def _check_language_patterns(self, profile_data: Dict[str, Any]) -> float:
        """
        Check for suspicious language patterns

        Returns:
            Score from 0.0 (suspicious patterns) to 1.0 (natural patterns)
        """
        posts = profile_data.get("posts", [])

        if not posts:
            return 0.5  # Neutral score if no posts

        # Default to a good score
        language_score = 0.8

        # Extract all content
        all_content = " ".join([
            str(post.get("text") or post.get("content") or post.get("full_text") or "")
            for post in posts
        ])

        # Check for repeated phrases
        repeated_phrases = self._find_repeated_phrases(all_content)
        if repeated_phrases:
            language_score -= 0.2 * len(repeated_phrases)

        # Check for excessive hashtags
        hashtag_ratio = self._calculate_hashtag_ratio(posts)
        if hashtag_ratio > 0.3:  # More than 30% hashtags is suspicious
            language_score -= 0.2

        # Check for spammy content
        if self._contains_spam_patterns(all_content):
            language_score -= 0.3

        return max(0.0, min(1.0, language_score))

    def _extract_posting_times(self, posts: List[Dict[str, Any]]) -> List[datetime]:
        """Extract posting times from posts"""
        times = []

        for post in posts:
            time_str = post.get("created_at", "")
            try:
                post_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
                times.append(post_time)
            except (ValueError, TypeError):
                # Skip invalid timestamps
                continue

        return sorted(times)

    def _detect_regular_intervals(self, timestamps: List[datetime]) -> bool:
        """
        Detect if posts are made at suspiciously regular intervals

        Returns:
            Boolean indicating if regular posting intervals detected
        """
        if len(timestamps) < 6:
            return False  # Need enough data points

        # Calculate time differences between posts
        intervals = []
        for i in range(1, len(timestamps)):
            diff_seconds = (timestamps[i] - timestamps[i - 1]).total_seconds()
            intervals.append(diff_seconds)

        # Check for consistent intervals (within 5% variance)
        if len(intervals) >= 5:
            avg_interval = sum(intervals) / len(intervals)
            consistent_count = sum(
                1
                for interval in intervals
                if abs(interval - avg_interval) < 0.05 * avg_interval
            )

            # If more than 50% of intervals are consistent, flag as suspicious
            if consistent_count > len(intervals) * 0.5:
                return True

        return False

    def _has_abnormal_engagement(self, posts: List[Dict[str, Any]]) -> bool:
        """
        Check if engagement metrics are suspiciously high

        Returns:
            Boolean indicating abnormal engagement
        """
        if not posts:
            return False

        # Calculate average likes and comments
        total_likes = sum(post.get("likes", 0) for post in posts)

        # Get comments or replies depending on platform
        total_comments = sum(
            post.get("comments", 0) + post.get("replies", 0) for post in posts
        )

        avg_likes = total_likes / len(posts)
        avg_comments = total_comments / len(posts)

        # These thresholds would be calibrated based on platform norms
        return avg_likes > 1000 and avg_comments > 200

    def _find_repeated_phrases(self, text: str) -> List[str]:
        """Find suspiciously repeated phrases in content"""
        # This is a simplified implementation
        # Real implementation would use more sophisticated text analysis

        # Extract 3-5 word phrases
        words = text.lower().split()
        phrases = []

        for length in range(3, 6):
            if len(words) <= length:
                continue

            for i in range(len(words) - length + 1):
                phrase = " ".join(words[i : i + length])
                phrases.append(phrase)

        # Count phrases and find those repeated suspiciously often
        phrase_counts = {}
        for phrase in phrases:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        # Filter to find repeated phrases
        repeated = [phrase for phrase, count in phrase_counts.items() if count >= 3]

        return repeated[:3]  # Return top 3 repeated phrases

    def _calculate_hashtag_ratio(self, posts: List[Dict[str, Any]]) -> float:
        """Calculate ratio of hashtags to content"""
        total_length = 0
        hashtag_length = 0

        for post in posts:
            content = str(post.get("text") or post.get("content") or post.get("full_text") or "")
            total_length += len(content)

            # Count hashtags
            hashtags = re.findall(r"#\w+", content)
            hashtag_length += sum(len(tag) for tag in hashtags)

        if total_length == 0:
            return 0.0

        return hashtag_length / total_length

    def _contains_spam_patterns(self, text: str) -> bool:
        """Check for common spam patterns in text"""
        # Look for common spam indicators
        spam_patterns = [
            r"(?i)buy now",
            r"(?i)click here",
            r"(?i)limited time offer",
            r"(?i)discount code",
            r"(?i)earn money fast",
            r"(?i)www\.[a-z0-9-]+\.[a-z]{2,}",  # Simple URL pattern
            r"(?i)call now",
            r"(?i)\d+% off",
        ]

        # Check each pattern
        for pattern in spam_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _generate_confidence_assessment(
        self,
        overall_score: float,
        consistency_score: float,
        activity_score: float,
        verification_status: bool,
        account_age_score: float,
        language_score: float,
    ) -> Tuple[str, List[str]]:
        """
        Generate confidence level and flags for the assessment

        Returns:
            Tuple of (confidence_level, flags)
        """
        flags = []

        # Set confidence level based on overall score
        if overall_score >= 0.8:
            confidence_level = "high"
        elif overall_score >= 0.6:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        # Generate specific flags based on component scores
        if consistency_score < 0.5:
            flags.append("Inconsistent profile behavior")

        if activity_score < 0.5:
            flags.append("Suspicious activity patterns")

        if not verification_status:
            flags.append("Account not verified")

        if account_age_score < 0.3:
            flags.append("Very new account")

        if language_score < 0.5:
            flags.append("Suspicious language patterns")

        return confidence_level, flags


# ---------------------------------------------------------------------------
# Benchmark evaluation
# ---------------------------------------------------------------------------
# A score nobody can falsify is marketing, not a measurement. This turns a
# labelled set of accounts into precision/recall for the authenticity verdict,
# and refuses to report a number when the sample is too small to mean anything.

BENCHMARK_MIN_SAMPLE = 20


def validate_benchmark_labels(accounts, sources=None):
    """Split labels into usable and unusable, citing why each was excluded.

    An ``inauthentic`` label is only worth as much as the source behind it, so a
    row must name a ``source_ref`` that exists in ``sources``. Rows without one
    are dropped instead of silently counted as ground truth.
    """
    known = {str(s.get("id")) for s in (sources or []) if s.get("id")}
    usable, rejected = [], []
    for row in accounts or []:
        if not row.get("is_inauthentic"):
            usable.append(row)
            continue
        ref = row.get("source_ref")
        if not ref:
            rejected.append({"profile_id": row.get("profile_id"),
                             "reason": "inauthentic label without a source_ref"})
        elif known and str(ref) not in known:
            rejected.append({"profile_id": row.get("profile_id"),
                             "reason": f"source_ref '{ref}' is not in sources"})
        elif not (row.get("label_reason") or "").strip():
            rejected.append({"profile_id": row.get("profile_id"),
                             "reason": "inauthentic label without the platform's stated reason"})
        else:
            usable.append(row)
    return {"usable": usable, "rejected": rejected}


def evaluate_authenticity_benchmark(scored, labels, threshold=0.5):
    """Score predictions against ground-truth labels.

    ``scored``  - iterable of dicts with platform/profile_id/identifier and a
                  numeric ``bot_likelihood``.
    ``labels``  - iterable of dicts with the same identifier and a boolean
                  ``is_inauthentic`` plus ``label_source`` describing why it is
                  trusted.

    Returns per-account rows, a confusion matrix for the "inauthentic" class,
    and explicit warnings. No metric is reported when there are no usable rows.
    """
    label_map = {}
    for row in labels or []:
        key = (str(row.get("platform", "")).lower(), str(row.get("profile_id", "")).lower())
        label_map[key] = row

    rows, warnings = [], []
    for item in scored or []:
        key = (str(item.get("platform", "")).lower(), str(item.get("profile_id", "")).lower())
        truth = label_map.get(key)
        likelihood = item.get("bot_likelihood")
        if truth is None or not isinstance(likelihood, (int, float)):
            continue
        predicted = likelihood >= threshold
        actual = bool(truth.get("is_inauthentic"))
        rows.append({
            "platform": key[0],
            "profile_id": key[1],
            "bot_likelihood": round(float(likelihood), 3),
            "predicted_inauthentic": predicted,
            "actual_inauthentic": actual,
            "correct": predicted == actual,
            "label_source": truth.get("label_source"),
        })

    if not rows:
        return {
            "n": 0,
            "usable": False,
            "threshold": threshold,
            "rows": [],
            "warnings": ["No scored accounts matched a label; nothing can be measured yet."],
        }

    tp = sum(1 for r in rows if r["predicted_inauthentic"] and r["actual_inauthentic"])
    fp = sum(1 for r in rows if r["predicted_inauthentic"] and not r["actual_inauthentic"])
    fn = sum(1 for r in rows if not r["predicted_inauthentic"] and r["actual_inauthentic"])
    tn = sum(1 for r in rows if not r["predicted_inauthentic"] and not r["actual_inauthentic"])

    precision = round(tp / (tp + fp), 3) if (tp + fp) else None
    recall = round(tp / (tp + fn), 3) if (tp + fn) else None
    f1 = (round(2 * precision * recall / (precision + recall), 3)
          if precision and recall else None)

    if len(rows) < BENCHMARK_MIN_SAMPLE:
        warnings.append(
            f"Only {len(rows)} labelled account(s); below {BENCHMARK_MIN_SAMPLE} the "
            "figures are indicative at best and must not be quoted as accuracy."
        )
    if not any(r["actual_inauthentic"] for r in rows):
        warnings.append(
            "No inauthentic account is in the scored set, so recall and precision are "
            "undefined: the only thing measured is how often a real account is wrongly "
            "flagged (false-positive rate)."
        )
    sources = {r["label_source"] for r in rows if r.get("label_source")}
    if len(sources) <= 1:
        warnings.append(
            "Labels come from a single source family, so agreement partly reflects that "
            "source's selection criteria rather than independent ground truth."
        )

    has_positives = (tp + fn) > 0
    return {
        "n": len(rows),
        "usable": len(rows) >= BENCHMARK_MIN_SAMPLE and has_positives,
        "threshold": threshold,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        # A set of only-authentic accounts scores 100% "accuracy" while measuring
        # nothing, so accuracy is withheld until at least one positive exists.
        "accuracy": round((tp + tn) / len(rows), 3) if has_positives else None,
        "false_positive_rate": round(fp / (fp + tn), 3) if (fp + tn) else None,
        "rows": rows,
        "warnings": warnings,
    }
