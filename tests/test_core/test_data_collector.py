"""Tests for the data collector module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from app.core.data_collector import (
    DataCollector,
    DataCollectionError,
)

# Mock Data
MOCK_TWITTER_PROFILE = {
    "user_id": "123456",
    "username": "testuser",
    "display_name": "Test User",
    "bio": "Test bio",
    "followers_count": 1000,
    "following_count": 500,
    "posts_count": 1500,
    "verified": True,
    "created_at": datetime.now().isoformat(),
    "profile_image_url": "https://example.com/image.jpg",
    "metadata": {"platform": "twitter", "is_real_data": True},
    "raw_data": {}
}

MOCK_TWITTER_POSTS = [
    {
        "id": "tweet123",
        "text": "Test tweet",
        "created_at": datetime.now().isoformat(),
        "likes_count": 20,
        "retweets_count": 10,
        "replies_count": 5,
        "is_retweet": False
    }
]

@pytest.fixture
def mock_scrape_client():
    """Mock ScrapeCreators client"""
    client = Mock()
    client.get_twitter_profile.return_value = MOCK_TWITTER_PROFILE
    client.get_twitter_posts.return_value = MOCK_TWITTER_POSTS
    
    # Add other platform mocks as needed
    client.get_facebook_profile.return_value = {**MOCK_TWITTER_PROFILE, "metadata": {"platform": "facebook"}}
    client.get_facebook_posts.return_value = []
    
    return client

@patch("app.core.data_collector.get_scrape_client")
def test_data_collector_initialization(mock_get_client, mock_scrape_client):
    """Test DataCollector initialization"""
    mock_get_client.return_value = mock_scrape_client
    
    collector = DataCollector("twitter", rate_limit=100)
    assert collector.platform == "twitter"
    assert collector.rate_limit == 100
    assert collector.scrape_client == mock_scrape_client

@patch("app.core.data_collector.get_scrape_client")
def test_collect_twitter_data(mock_get_client, mock_scrape_client):
    """Test collecting Twitter profile data"""
    mock_get_client.return_value = mock_scrape_client
    
    collector = DataCollector("twitter")
    profile_data = collector.collect_profile_data("testuser")
    
    # Check if correct method was called
    mock_scrape_client.get_twitter_profile.assert_called_with("testuser")
    
    assert profile_data["username"] == "testuser"
    assert "posts" in profile_data
    assert "metadata" in profile_data
    assert profile_data["metadata"]["platform"] == "twitter"

@patch("app.core.data_collector.get_scrape_client")
def test_collect_unsupported_platform(mock_get_client, mock_scrape_client):
    """An unsupported platform reports failure instead of inventing a profile."""
    mock_get_client.return_value = mock_scrape_client

    collector = DataCollector("unsupported_platform")
    profile_data = collector.collect_profile_data("testuser")

    assert profile_data["collection_failed"] is True
    assert profile_data["is_mock_data"] is False
    assert profile_data["posts"] == []
    # No generated metrics may masquerade as collected ones.
    assert "follower_count" not in profile_data

@patch("app.core.data_collector.get_scrape_client")
def test_mock_data_generation(mock_get_client, mock_scrape_client):
    """Test that explicit mock data is generated correctly"""
    mock_get_client.return_value = mock_scrape_client
    
    collector = DataCollector("twitter", use_mock_data=True)
    profile_data = collector.collect_profile_data("testuser")
    
    # Should NOT call API
    mock_scrape_client.get_twitter_profile.assert_not_called()
    
    assert profile_data["username"] == "testuser"
    assert profile_data["metadata"]["is_mock_data"] is True
    assert "posts" in profile_data
    assert len(profile_data["posts"]) > 0

@patch("app.core.data_collector.get_scrape_client")
def test_api_error_does_not_fabricate(mock_get_client, mock_scrape_client):
    """An API error must surface as a failure, not as generated data."""
    mock_get_client.return_value = mock_scrape_client
    
    # Make API raise exception
    mock_scrape_client.get_twitter_profile.side_effect = Exception("API Error")
    
    collector = DataCollector("twitter")
    profile_data = collector.collect_profile_data("testuser")
    
    assert profile_data["collection_failed"] is True
    assert profile_data["metadata"]["api_errors"] is not None
    assert profile_data["metadata"]["is_real_data"] is False
    assert "follower_count" not in profile_data
