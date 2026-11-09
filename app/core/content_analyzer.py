# Vanta: Social Media Profile Analyzer
# A comprehensive framework for analyzing public social media profiles

import os
import json
import datetime
import argparse
import logging
from typing import Dict, List, Any, Optional, Tuple
import re
from collections import Counter

from app.utils.helpers import parse_timestamp, posting_cadence


class ContentAnalyzer:
    """Analyzes social media content using NLP and other techniques"""

    def __init__(self, nlp_model: str = "default", sentiment_analyzer: bool = True):
        """
        Initialize content analyzer with specified models

        Args:
            nlp_model: Name of NLP model to use
            sentiment_analyzer: Whether to include sentiment analysis
        """
        self.nlp_model = nlp_model
        self.use_sentiment = sentiment_analyzer
        self.logger = logging.getLogger("Vanta.ContentAnalyzer")
        # TODO: Load actual NLP models based on configuration

    def analyze_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform complete content analysis on a social media profile

        Args:
            profile_data: Dictionary containing profile data

        Returns:
            Dictionary with analysis results
        """
        self.logger.info("Starting profile content analysis")
        posts = profile_data.get("posts", [])

        # Extract all text content for analysis
        text_content = self._extract_text_content(profile_data)

        # Calculate various metrics
        posting_frequency = self._calculate_posting_frequency(posts)
        topics = self._identify_topics(posts)
        sentiment = self._analyze_sentiment(posts) if self.use_sentiment else None
        writing_style = self._analyze_writing_style(posts)
        personality_traits = self._infer_personality(posts, profile_data)
        interests = self._analyze_interests(text_content, profile_data)

        # Generate timeline from profile data
        timeline = self._generate_timeline(profile_data)

        # Analyze sentiment trends
        sentiment_trends = self._analyze_sentiment_trends(profile_data)

        # Generate summary of findings
        summary = self._generate_summary(
            profile_data, posting_frequency, topics, sentiment, personality_traits
        )

        # Check if this is mock data
        metadata = profile_data.get("metadata", {})
        is_mock = metadata.get("is_mock_data", False)
        
        if is_mock:
            mock_disclaimer = "This analysis is based on mock data generated for demonstration purposes. In a production environment, this would be replaced with actual social media data analysis."
        else:
            mock_disclaimer = None

        # Compile results
        analysis_results = {
            "summary": summary,
            "posting_patterns": {
                "frequency": posting_frequency,
                "activity_hours": self._identify_activity_hours(posts),
            },
            "content_topics": topics,
            "writing_style": writing_style,
            "personality_traits": personality_traits,
            "interests": interests,
            "timeline": timeline,
            "sentiment_trends": sentiment_trends,
        }

        if sentiment:
            analysis_results["sentiment"] = sentiment

        if mock_disclaimer:
            analysis_results["mock_data_disclaimer"] = mock_disclaimer

        return analysis_results

    def _generate_summary(
        self,
        profile_data: Dict[str, Any],
        posting_frequency: Dict[str, Any],
        topics: Dict[str, Any],
        sentiment: Optional[Dict[str, Any]],
        personality_traits: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a summary of the profile analysis

        Args:
            profile_data: Complete profile data
            posting_frequency: Posting frequency analysis
            topics: Content topics analysis
            sentiment: Sentiment analysis results
            personality_traits: Personality traits analysis

        Returns:
            Dictionary with summary information
        """
        # Get profile basics
        platform = profile_data.get("metadata", {}).get("platform", "social media")
        profile_name = profile_data.get("profile", {}).get("username", "this profile")

        # Activity level
        posts_count = len(profile_data.get("posts", []))
        daily_avg = posting_frequency.get("daily_average", 0)

        if daily_avg > 3:
            activity_level = "very active"
        elif daily_avg > 1:
            activity_level = "active"
        elif daily_avg > 0.3:  # About 2-3 times per week
            activity_level = "moderately active"
        else:
            activity_level = "occasionally active"

        # Top topics/interests
        top_topics = [topic for topic, _ in topics.get("top_topics", [])][:2]
        top_topics_text = " and ".join(top_topics) if top_topics else "various topics"

        # Sentiment summary
        sentiment_text = "neutral tone"
        if sentiment:
            sentiment_label = sentiment.get("overall_sentiment", {}).get("label")
            if sentiment_label == "positive":
                sentiment_text = "generally positive tone"
            elif sentiment_label == "negative":
                sentiment_text = "generally critical tone"

        # Create summary text components
        profile_summary = f"Based on the analysis of {posts_count} posts, {profile_name} appears to be {activity_level} on {platform}."
        content_summary = (
            f"Content primarily focuses on {top_topics_text} with a {sentiment_text}."
        )

        # Extract top personality traits
        top_traits = []
        for trait, value in personality_traits.items():
            if value > 0.7:
                top_traits.append(trait.replace("_", " "))

        personality_summary = ""
        if top_traits:
            traits_text = ", ".join(top_traits)
            personality_summary = f"Analysis suggests tendencies toward {traits_text}."

        return {
            "profile_overview": profile_summary,
            "content_overview": content_summary,
            "personality_overview": personality_summary,
            "post_count": posts_count,
            "activity_level": activity_level,
            "main_topics": top_topics,
            "general_sentiment": sentiment_text,
        }

    def _extract_text_content(self, profile_data: Dict[str, Any]) -> str:
        """
        Extract all text content from profile data

        Args:
            profile_data: Dictionary containing profile data

        Returns:
            Concatenated text content from profile
        """
        all_text = []

        # Extract profile bio/description
        if "profile" in profile_data:
            if "bio" in profile_data["profile"]:
                all_text.append(profile_data["profile"]["bio"])
            elif "description" in profile_data["profile"]:
                all_text.append(profile_data["profile"]["description"])

        # Extract post content
        for post in profile_data.get("posts", []):
            # Check all possible content fields
            content = post.get("text") or post.get("content") or post.get("full_text") or post.get("message") or post.get("caption")
            if content:
                all_text.append(str(content))

        # Extract media captions
        for media in profile_data.get("media", []):
            if "caption" in media:
                all_text.append(media["caption"])

        return " ".join(all_text)

    def _calculate_posting_frequency(
        self, posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate posting frequency metrics.

        The rate comes from the shared helper (posts per week over the span the
        samples cover), so this figure matches the one stored in the subject's
        snapshot instead of being computed a second way.
        """
        if not posts:
            return {"daily_average": 0, "weekly_average": 0, "monthly_average": 0}

        raw_when = [post.get("created_at") or post.get("date") or post.get("publishTime")
                    for post in posts if isinstance(post, dict)]
        cadence = posting_cadence(raw_when)

        dates = []
        for value in raw_when:
            parsed = parse_timestamp(value)
            if parsed:
                dates.append(parsed.date())

        if not dates or cadence["posts_per_week"] is None:
            return {"daily_average": 0, "weekly_average": 0, "monthly_average": 0}

        date_counts = Counter(dates)
        weekly_avg = cadence["posts_per_week"]
        daily_avg = weekly_avg / 7
        monthly_avg = daily_avg * 30

        # Find most active days
        active_days = date_counts.most_common(3)
        active_days = [(day.strftime("%Y-%m-%d"), count) for day, count in active_days]

        return {
            "daily_average": round(daily_avg, 2),
            "weekly_average": round(weekly_avg, 2),
            "monthly_average": round(monthly_avg, 2),
            "most_active_days": active_days,
        }

    def _identify_activity_hours(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify hours of day with most activity"""
        hours = []

        for post in posts:
            try:
                time_str = post.get("created_at", "") or post.get("date", "")
                # Extract hour from ISO format timestamp
                hour = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").hour
                hours.append(hour)
            except (ValueError, TypeError):
                # Skip posts with invalid timestamps
                continue

        # Count posts per hour
        hour_counts = Counter(hours)

        # Find peak hours (top 3)
        peak_hours = hour_counts.most_common(3)

        # Group into time periods
        morning = sum(hour_counts.get(h, 0) for h in range(5, 12))  # 5am-11am
        afternoon = sum(hour_counts.get(h, 0) for h in range(12, 17))  # 12pm-4pm
        evening = sum(hour_counts.get(h, 0) for h in range(17, 22))  # 5pm-9pm
        night = sum(hour_counts.get(h, 0) for h in range(22, 24)) + sum(
            hour_counts.get(h, 0) for h in range(0, 5)
        )  # 10pm-4am

        total = morning + afternoon + evening + night
        if total == 0:
            total = 1  # Avoid division by zero

        return {
            "peak_hours": peak_hours,
            "time_periods": {
                "morning": {
                    "count": morning,
                    "percentage": round(morning * 100 / total, 1),
                },
                "afternoon": {
                    "count": afternoon,
                    "percentage": round(afternoon * 100 / total, 1),
                },
                "evening": {
                    "count": evening,
                    "percentage": round(evening * 100 / total, 1),
                },
                "night": {"count": night, "percentage": round(night * 100 / total, 1)},
            },
        }

    def _identify_topics(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify main topics from posts"""
        # Extract all text content
        all_text = " ".join([
            str(post.get("text") or post.get("content") or post.get("full_text") or post.get("message") or "")
            for post in posts
        ])
        all_text = all_text.lower()

        # Extract hashtags
        hashtags = []
        for post in posts:
            post_hashtags = post.get("hashtags", [])
            if post_hashtags:
                hashtags.extend(post_hashtags)
            else:
                # Try to extract hashtags from content if not provided
                content = str(post.get("text") or post.get("content") or post.get("full_text") or "")
                if content:
                    found_tags = re.findall(r"#(\w+)", content)
                    hashtags.extend(["#" + tag for tag in found_tags])

        # Count hashtag frequency
        hashtag_counts = Counter(hashtags).most_common(10)

        # Basic topic detection based on keywords
        # In a real system, this would use topic modeling or NLP classification
        topics = {
            "politics": self._count_keyword_matches(
                all_text, ["politics", "election", "vote", "government", "president"]
            ),
            "technology": self._count_keyword_matches(
                all_text,
                ["tech", "technology", "computer", "software", "app", "digital"],
            ),
            "entertainment": self._count_keyword_matches(
                all_text, ["movie", "music", "concert", "TV", "show", "celebrity"]
            ),
            "sports": self._count_keyword_matches(
                all_text, ["sports", "game", "team", "win", "player", "score"]
            ),
            "lifestyle": self._count_keyword_matches(
                all_text, ["food", "travel", "fashion", "home", "fitness"]
            ),
            "business": self._count_keyword_matches(
                all_text, ["business", "company", "market", "startup", "entrepreneur"]
            ),
        }

        # Find top topics
        top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "top_hashtags": hashtag_counts,
            "topic_distribution": topics,
            "top_topics": top_topics,
        }

    def _count_keyword_matches(self, text: str, keywords: List[str]) -> int:
        """Count occurrences of keywords in text"""
        return sum(text.count(keyword.lower()) for keyword in keywords)

    def _analyze_sentiment(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sentiment in posts"""
        # In a real system, this would use a proper sentiment analysis model
        # Here, we use a simple approach based on keyword matching

        positive_words = [
            "happy",
            "great",
            "excellent",
            "good",
            "love",
            "amazing",
            "best",
            "awesome",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "hate",
            "worst",
            "sad",
            "angry",
            "disappointed",
        ]

        post_sentiments = []

        for post in posts:
            content = str(post.get("text") or post.get("content") or post.get("full_text") or "").lower()
            pos_count = sum(content.count(word) for word in positive_words)
            neg_count = sum(content.count(word) for word in negative_words)

            # Calculate simple sentiment score
            if pos_count > neg_count:
                sentiment = "positive"
                score = min(1.0, 0.5 + (pos_count - neg_count) * 0.1)
            elif neg_count > pos_count:
                sentiment = "negative"
                score = max(-1.0, -0.5 - (neg_count - pos_count) * 0.1)
            else:
                sentiment = "neutral"
                score = 0.0

            post_sentiments.append(
                {
                    "post_id": post.get("id", ""),
                    "sentiment": sentiment,
                    "score": score,
                }
            )

        # Calculate overall sentiment
        if not post_sentiments:
            avg_score = 0.0
        else:
            avg_score = sum(s["score"] for s in post_sentiments) / len(post_sentiments)

        if avg_score > 0.2:
            overall = "positive"
        elif avg_score < -0.2:
            overall = "negative"
        else:
            overall = "neutral"

        # Count sentiment distribution
        sentiment_counts = Counter(s["sentiment"] for s in post_sentiments)

        return {
            "overall_sentiment": {"label": overall, "score": round(avg_score, 2)},
            "distribution": {
                "positive": sentiment_counts.get("positive", 0),
                "neutral": sentiment_counts.get("neutral", 0),
                "negative": sentiment_counts.get("negative", 0),
            },
            "post_sentiments": post_sentiments[:5],  # Return only first 5 for brevity
        }

    def _analyze_writing_style(
        self, posts: List[Dict[str, Any]] or str
    ) -> Dict[str, Any]:
        """Analyze writing style patterns"""
        if not posts:
            return {}

        # Extract all text content
        if isinstance(posts, str):
            # If input is already a string, use it directly
            all_text = posts
        else:
            # If input is a list of posts, extract the content
            all_text = " ".join([
                str(post.get("text") or post.get("content") or post.get("full_text") or "")
                for post in posts
            ])

        # Basic metrics
        word_count = len(re.findall(r"\b\w+\b", all_text))
        sentences = re.split(r"[.!?]+", all_text)
        sentence_count = len([s for s in sentences if s.strip()])

        # Avoid division by zero
        if sentence_count == 0:
            sentence_count = 1

        avg_sentence_length = word_count / sentence_count

        # Simple vocabulary diversity
        words = re.findall(r"\b\w+\b", all_text.lower())
        unique_words = len(set(words))
        vocabulary_diversity = unique_words / max(1, word_count)

        # Simple formality and complexity metrics
        long_words = sum(1 for word in words if len(word) > 6)
        complex_word_ratio = long_words / max(1, word_count)
        formal_words = self._count_keyword_matches(
            all_text.lower(),
            ["therefore", "however", "consequently", "furthermore", "nevertheless"],
        )
        formal_ratio = formal_words / max(1, word_count) * 10  # Scale up for visibility

        # Emotional content
        emotional_words = self._count_keyword_matches(
            all_text.lower(),
            ["love", "hate", "happy", "sad", "angry", "excited", "afraid", "proud"],
        )
        emotional_ratio = (
            emotional_words / max(1, word_count) * 5
        )  # Scale up for visibility

        # Results with normalized average_sentence_length
        return {
            "average_sentence_length": round(avg_sentence_length, 1),
            "vocabulary_diversity": round(vocabulary_diversity, 2),
            "complexity": round(
                min((complex_word_ratio * 2) + (avg_sentence_length / 25), 1.0), 2
            ),
            "formality": round(min(formal_ratio + 0.3, 1.0), 2),
            "emotional_tone": round(min(emotional_ratio, 1.0), 2),
            "word_count": word_count,
            "normalized_sentence_length": round(min(avg_sentence_length / 15, 1.0), 2),
        }

    def _infer_personality(
        self, posts: List[Dict[str, Any]], profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Infer personality traits based on content
        This is a simplified placeholder - real implementation would use psycholinguistic models
        """
        # Extract all text content
        all_text = " ".join([
            str(post.get("text") or post.get("content") or post.get("full_text") or "")
            for post in posts
        ])
        all_text = all_text.lower()

        # For the sake of simplicity in tests, return default values
        # In a real system, this would use NLP and linguistic analysis
        return {
            "extraversion": 0.5,
            "openness": 0.5,
            "conscientiousness": 0.5,
        }

    def _analyze_interests(
        self, text_content: str, profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze user interests from content

        Args:
            text_content: Extracted text content
            profile_data: Complete profile data

        Returns:
            Dictionary of identified interests
        """
        # Simple placeholder implementation for tests
        # In a real system, this would use topic modeling and interest extraction
        interests = {}

        # Extract hashtags as potential interests
        hashtags = []
        for post in profile_data.get("posts", []):
            content = str(post.get("text") or post.get("content") or post.get("full_text") or "")
            if content:
                found_tags = re.findall(r"#(\w+)", content)
                hashtags.extend(found_tags)

        # Count hashtag frequency
        tag_counts = Counter(hashtags)

        # Convert top hashtags to interests
        for tag, count in tag_counts.most_common(5):
            interests[tag] = {
                "confidence": min(0.95, 0.5 + count / 10),
                "mentions": count,
                "source": "hashtags",
            }

        return interests

    def _generate_timeline(self, profile_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate chronological timeline of user activity

        Args:
            profile_data: Profile data dictionary

        Returns:
            List of timeline events
        """
        timeline = []

        # Add profile creation if available
        if "profile" in profile_data:
            profile = profile_data["profile"]
            join_date = profile.get("created_at") or profile.get("join_date")
            if join_date:
                timeline.append(
                    {
                        "date": join_date,
                        "type": "account_creation",
                        "description": "Account created",
                    }
                )

        # Add posts to timeline
        for post in profile_data.get("posts", []):
            date = post.get("created_at") or post.get("date")
            content = str(post.get("text") or post.get("content") or post.get("full_text") or "")
            if date:
                timeline.append(
                    {
                        "date": date,
                        "type": "post",
                        "description": content[:50]
                        + ("..." if len(content) > 50 else ""),
                    }
                )

        # Add media to timeline
        for media in profile_data.get("media", []):
            date = media.get("created_at") or media.get("date")
            if date:
                media_type = media.get("type", "media")
                timeline.append(
                    {
                        "date": date,
                        "type": media_type,
                        "description": media.get("caption", f"Shared {media_type}"),
                    }
                )

        # Sort timeline by date
        timeline.sort(key=lambda x: x["date"])

        return timeline

    def _analyze_sentiment_trends(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze sentiment trends over time

        Args:
            profile_data: Complete profile data

        Returns:
            Dictionary of sentiment analysis results
        """
        posts = profile_data.get("posts", [])
        if not posts:
            return {
                "overall_sentiment": {"label": "neutral", "score": 0.0},
                "distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "post_sentiments": [],
            }

        # Sort posts by date
        try:
            sorted_posts = sorted(
                posts,
                key=lambda p: p.get("created_at", "") or p.get("date", ""),
                reverse=False,
            )
        except:
            sorted_posts = posts  # If sorting fails, use original order

        # Generate time-based sentiment analysis
        post_sentiments = []
        sentiments_by_month = {}
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for post in sorted_posts:
            content = str(post.get("text") or post.get("content") or post.get("full_text") or "").lower()
            date_str = post.get("created_at", "") or post.get("date", "")

            # Simple sentiment scoring system
            pos_words = [
                "happy",
                "great",
                "excellent",
                "good",
                "love",
                "amazing",
                "best",
            ]
            neg_words = ["bad", "terrible", "awful", "hate", "worst", "sad", "angry"]

            pos_count = sum(content.count(word) for word in pos_words)
            neg_count = sum(content.count(word) for word in neg_words)

            # Calculate sentiment and score
            if pos_count > neg_count:
                sentiment = "positive"
                score = min(1.0, 0.5 + (pos_count - neg_count) * 0.1)
                positive_count += 1
            elif neg_count > pos_count:
                sentiment = "negative"
                score = max(-1.0, -0.5 - (neg_count - pos_count) * 0.1)
                negative_count += 1
            else:
                sentiment = "neutral"
                score = 0.0
                neutral_count += 1

            # Add to post sentiments
            post_sentiments.append(
                {
                    "post_id": post.get("id", ""),
                    "date": date_str,
                    "sentiment": sentiment,
                    "score": score,
                }
            )

            # Group by month
            try:
                month = date_str[:7]  # YYYY-MM
                if month not in sentiments_by_month:
                    sentiments_by_month[month] = {
                        "scores": [],
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0,
                    }

                sentiments_by_month[month]["scores"].append(score)
                sentiments_by_month[month][sentiment] += 1
            except:
                pass  # Skip if date parsing fails

        # Calculate monthly averages
        monthly_trend = []
        for month, data in sorted(sentiments_by_month.items()):
            if data["scores"]:
                avg_score = sum(data["scores"]) / len(data["scores"])
                monthly_trend.append(
                    {
                        "month": month,
                        "average_score": round(avg_score, 2),
                        "positive": data["positive"],
                        "neutral": data["neutral"],
                        "negative": data["negative"],
                    }
                )

        # Calculate overall sentiment
        total = len(post_sentiments)
        if total == 0:
            avg_score = 0.0
            overall = "neutral"
        else:
            avg_score = sum(ps["score"] for ps in post_sentiments) / total
            if avg_score > 0.2:
                overall = "positive"
            elif avg_score < -0.2:
                overall = "negative"
            else:
                overall = "neutral"

        return {
            "overall_sentiment": {"label": overall, "score": round(avg_score, 2)},
            "distribution": {
                "positive": positive_count,
                "neutral": neutral_count,
                "negative": negative_count,
            },
            "post_sentiments": post_sentiments[:5],  # Return only first 5 for brevity
            "monthly_trend": monthly_trend,
        }
