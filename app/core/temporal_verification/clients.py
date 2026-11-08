"""
Vanta: Temporal Verification API Clients (Layer 5)
API clients for timeline and context verification
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("Vanta.TemporalVerification")


class GDELTClient:
    """
    GDELT (Global Database of Events, Language, and Tone) API client
    https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GDELT_API_KEY")
        self.base_url = "https://api.gdeltproject.org/api/v2"
        
        # GDELT themes for Bangladesh/politics
        self.themes = {
            "politics": "POLITICS",
            "government": "GOVERNMENT", 
            "protest": "PROTEST",
            "violence": "VIOLENCE",
            "economics": "ECONOMICS"
        }
    
    def search_events(self, 
                     claim_text: str,
                     start_date: str,
                     end_date: str,
                     country: str = None) -> List[Dict[str, Any]]:
        """
        Search GDELT for events matching claim
        
        Args:
            claim_text: Claim to verify
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            country: Country code (BD for Bangladesh)
            
        Returns:
            List of matching events
        """
        try:
            # Extract keywords for search
            keywords = self._extract_keywords(claim_text)
            
            query = f"{keywords} sourcelang:eng" + (f" location:{country}" if country else "")
            params = {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": 50,
                "startdatetime": f"{start_date}000000",
                "enddatetime": f"{end_date}235959"
            }
            
            response = requests.get(
                f"{self.base_url}/doc/doc",
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"GDELT API error: {response.status_code}")
                return []
            
            data = response.json()
            articles = data.get("articles", [])
            
            events = []
            for article in articles:
                event = {
                    "source": "gdelt",
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "date": article.get("seendate", ""),
                    "domain": article.get("domain", ""),
                    "language": article.get("language", ""),
                    "country": country,
                    "relevance_score": self._calculate_relevance(claim_text, article),
                    "raw_data": article
                }
                events.append(event)
            
            logger.info(f"GDELT found {len(events)} events for claim")
            return events
            
        except Exception as e:
            logger.error(f"GDELT search error: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> str:
        """Extract search keywords from claim text"""
        # Simple keyword extraction (replace with NLP later)
        keywords = text.lower().split()[:10]
        return " ".join(keywords)
    
    def _calculate_relevance(self, claim_text: str, article: Dict) -> float:
        """Relevance via TF-IDF cosine (labelled, see matcher.tfidf_cosine).
        Old word-overlap / len(claim_words) scored 0.26 for genuinely
        relevant articles and rejected them."""
        try:
            from app.core.fact_check.matcher import tfidf_cosine
            return tfidf_cosine(claim_text, article.get("title", ""))
        except Exception:
            return 0.0


class WaybackClient:
    """
    Wayback Machine (archive.org) API client
    https://archive.org/help/wayback_api.php
    """
    
    def __init__(self):
        self.base_url = "https://archive.org/wayback/available"
    
    def find_snapshots(self, 
                      url: str,
                      claim_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find Wayback Machine snapshots for a URL
        
        Args:
            url: URL to check
            claim_date: Date claim was made (YYYY-MM-DD)
            
        Returns:
            List of snapshots
        """
        try:
            params = {"url": url}
            
            if claim_date:
                params["timestamp"] = claim_date
            
            response = requests.get(self.base_url, params=params, timeout=10)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            snapshots = []
            
            # Parse available snapshots
            archives = data.get("archived_snapshots", {})
            
            for key, snapshot in archives.items():
                if snapshot.get("available") and snapshot.get("status") == "200":
                    snapshot_data = {
                        "source": "wayback_machine",
                        "url": snapshot.get("url", ""),
                        "timestamp": snapshot.get("timestamp", ""),
                        "status": snapshot.get("status", ""),
                        "original_url": url,
                        "available": True
                    }
                    
                    # Parse timestamp to date
                    if snapshot_data["timestamp"]:
                        try:
                            ts = snapshot_data["timestamp"]
                            date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                            snapshot_data["date"] = date_str
                        except:
                            snapshot_data["date"] = ""
                    
                    snapshots.append(snapshot_data)
            
            logger.info(f"Wayback found {len(snapshots)} snapshots for {url}")
            return snapshots
            
        except Exception as e:
            logger.error(f"Wayback API error: {e}")
            return []
    
    def verify_url_existence(self, url: str, claim_date: str) -> Dict[str, Any]:
        """
        Verify if URL existed at claim date
        """
        snapshots = self.find_snapshots(url, claim_date)
        
        if not snapshots:
            return {
                "verified": False,
                "message": "No snapshots found",
                "closest_snapshot": None
            }
        
        # Find closest snapshot to claim date
        closest = min(
            snapshots, 
            key=lambda x: abs(
                datetime.strptime(x.get("date", "9999-99-99"), "%Y-%m-%d") - 
                datetime.strptime(claim_date, "%Y-%m-%d")
            )
        )
        
        return {
            "verified": True,
            "message": f"URL existed near claim date",
            "closest_snapshot": closest,
            "snapshots_found": len(snapshots)
        }


class NewsAPIClient:
    """
    NewsAPI client for contemporaneous reporting verification
    https://newsapi.org/
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEWSAPI_KEY")
        self.base_url = "https://newsapi.org/v2"
        
        if not self.api_key:
            logger.warning("NewsAPI key not configured")
    
    def search_articles(self,
                       claim_text: str,
                       claim_date: str,
                       days_before: int = 7,
                       days_after: int = 7) -> List[Dict[str, Any]]:
        """
        Search news articles around claim date
        
        Args:
            claim_text: Claim to verify
            claim_date: Date claim was made (YYYY-MM-DD)
            days_before: Days before claim to search
            days_after: Days after claim to search
            
        Returns:
            List of news articles
        """
        if not self.api_key:
            logger.warning("NewsAPI key not available")
            return []
        
        try:
            # Calculate date range
            claim_dt = datetime.strptime(claim_date, "%Y-%m-%d")
            from_date = (claim_dt - timedelta(days=days_before)).strftime("%Y-%m-%d")
            to_date = (claim_dt + timedelta(days=days_after)).strftime("%Y-%m-%d")
            
            # Extract search terms
            search_terms = self._extract_search_terms(claim_text)
            
            params = {
                "q": search_terms,
                "from": from_date,
                "to": to_date,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 50,
                "apiKey": self.api_key
            }
            
            response = requests.get(
                f"{self.base_url}/everything",
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"NewsAPI error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            articles = data.get("articles", [])
            
            processed = []
            for article in articles:
                processed_article = {
                    "source": "newsapi",
                    "source_name": article.get("source", {}).get("name", ""),
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", ""),
                    "relevance_score": self._calculate_news_relevance(claim_text, article),
                    "raw_data": article
                }
                processed.append(processed_article)
            
            logger.info(f"NewsAPI found {len(processed)} articles")
            return processed
            
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return []
    
    def _extract_search_terms(self, text: str) -> str:
        """Extract search terms from claim text"""
        # Remove common words + punctuation. NewsAPI treats filler words (was/and/us)
        # as required terms and returns 0 results for e.g. "2020 us election was stolen".
        stopwords = {"the", "is", "are", "was", "were", "has", "have", "that", "this",
                     "and", "actually", "for", "with", "from", "were", "been", "will"}
        import re as _re
        cleaned = _re.sub(r"[^\w\s]", " ", text.lower())
        words = [w for w in cleaned.split() if w not in stopwords and len(w) > 2]
        return " ".join(words[:5])
    
    def _calculate_news_relevance(self, claim_text: str, article: Dict) -> float:
        """Relevance between claim and article via TF-IDF cosine over
        title+description (labelled tfidf in verifier output). The old
        word-overlap/len(claim_words) metric averaged 0.26 on 16 real
        articles for a true claim and wrongly set verified=False."""
        try:
            from app.core.fact_check.matcher import tfidf_cosine
            return tfidf_cosine(
                claim_text,
                f"{article.get('title', '')} {article.get('description', '')}")
        except Exception:
            return 0.0


class WikipediaClient:
    """
    Wikipedia API client for established facts
    https://www.mediawiki.org/wiki/API:Main_page
    """
    
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/api/rest_v1"
    
    def get_historical_fact(self, 
                           topic: str,
                           as_of_date: str) -> Optional[Dict[str, Any]]:
        """
        Get Wikipedia state as of a specific date
        
        Args:
            topic: Topic to look up
            as_of_date: Date to check (YYYY-MM-DD)
            
        Returns:
            Wikipedia state at that date
        """
        try:
            # Search for page
            search_url = f"https://en.wikipedia.org/w/api.php"
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": topic,
                "format": "json"
            }
            
            search_resp = requests.get(search_url, params=search_params, timeout=10,
                                     headers={"User-Agent": "Vanta-temporal/1.0"})
            if search_resp.status_code != 200:
                return None
            try:
                search_data = search_resp.json()
            except Exception:
                return None
            
            if not search_data.get("query", {}).get("search"):
                return None
            
            # Get first result
            page_id = search_data["query"]["search"][0]["pageid"]
            page_title = search_data["query"]["search"][0]["title"]
            
            # Historical state as of as_of_date: newest revision at/before
            # that date. Old code fetched the 50 OLDEST revisions
            # (rvdir=newer from page creation) and picked the closest among
            # them - for old articles that is decades off the target date.
            revision_params = {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content|timestamp",
                "rvlimit": 5,
                "rvstart": f"{as_of_date}T00:00:00Z",
                "rvdir": "older",
                "format": "json",
                "pageids": page_id
            }
            
            revision_resp = requests.get(search_url, params=revision_params, timeout=10,
                                       headers={"User-Agent": "Vanta-temporal/1.0"})
            if revision_resp.status_code != 200:
                return None
            try:
                revision_data = revision_resp.json()
            except Exception:
                return None
            
            revisions = revision_data.get("query", {}).get("pages", {}).get(str(page_id), {}).get("revisions", [])
            
            # Find closest revision to as_of_date
            closest_rev = None
            min_diff = None
            
            for rev in revisions:
                rev_date = rev.get("timestamp", "")[:10]  # YYYY-MM-DD
                if not rev_date:
                    continue
                
                diff = abs((datetime.strptime(rev_date, "%Y-%m-%d") - 
                          datetime.strptime(as_of_date, "%Y-%m-%d")).days)
                
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest_rev = rev
            
            if closest_rev:
                return {
                    "source": "wikipedia",
                    "topic": topic,
                    "page_title": page_title,
                    "revision_date": closest_rev.get("timestamp", "")[:10],
                    "revision_id": closest_rev.get("revid"),
                    "content_preview": closest_rev.get("content", "")[:500],
                    "days_difference": min_diff
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Wikipedia API error: {e}")
            return None


def create_temporal_client(source: str, **kwargs):
    """
    Factory function for temporal verification clients
    
    Args:
        source: "gdelt", "wayback", "newsapi", "wikipedia"
    """
    if source == "gdelt":
        return GDELTClient(**kwargs)
    elif source == "wayback":
        return WaybackClient(**kwargs)
    elif source == "newsapi":
        return NewsAPIClient(**kwargs)
    elif source == "wikipedia":
        return WikipediaClient(**kwargs)
    else:
        raise ValueError(f"Unknown temporal source: {source}")