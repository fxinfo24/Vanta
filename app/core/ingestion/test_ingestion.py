"""
Test the ingestion pipeline
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

from app.web.models import db
from app.web.models.verification import (
    SocialMediaPost, Claim, VerificationResult, 
    FactCheckSource, ExternalFactCheck
)
from app.core.ingestion.schemas import ApifyFacebookPost
from app.core.ingestion.lang_detect import detect_language


def test_language_detection():
    """Test language detection"""
    print("Testing language detection...")
    
    texts = [
        "The government announced new policies today.",
        "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।",
        "El gobierno anunció nuevas políticas hoy."
    ]
    
    for text in texts:
        lang, conf = detect_language(text, min_length=5)
        print(f"Text: {text[:50]}...")
        print(f"  Detected: {lang} (confidence: {conf})")
        print()


def test_schemas():
    """Test Pydantic schemas"""
    print("Testing Pydantic schemas...")
    
    # Create sample post data matching Apify format
    sample_post = {
        "facebookUrl": "https://www.facebook.com/sahab0769",
        "postId": "123456789",
        "pageName": "sahab0769",
        "url": "https://www.facebook.com/sahab0769/posts/123456789",
        "time": "2026-04-08T02:54:04.000Z",
        "timestamp": 1775616844,
        "user": {
            "id": "100003157204577",
            "name": "আহমেদ সাহাব",
            "profileUrl": "https://www.facebook.com/100003157204577",
            "profilePic": "https://example.com/photo.jpg"
        },
        "collaborators": [],
        "text": "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।",
        "likes": 101,
        "comments": 12,
        "shares": 16,
        "topReactionsCount": 4,
        "media": [],
        "feedbackId": "abc123",
        "reactionLikeCount": 88,
        "reactionLoveCount": 11,
        "reactionCareCount": 1,
        "reactionSadCount": 1
    }
    
    try:
        post = ApifyFacebookPost(**sample_post)
        print(f"✅ Schema validation passed")
        print(f"Post ID: {post.postId}")
        print(f"Language: {post.get_detected_language()}")
        print(f"Quality score: {post.quality_score()}")
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")


def test_database_connection():
    """Test database connection and model creation"""
    print("Testing database connection...")
    
    try:
        # Create an engine
        from app.web.database import engine
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print(f"✅ Database connection successful")
            
        # Test model creation
        # This would create tables if they don't exist
        from app.web.models import Base
        Base.metadata.create_all(engine)
        print(f"✅ Models registered")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")


def test_ingestor():
    """Test ingestor with sample data"""
    print("Testing ingestor with sample data...")
    
    from app.core.ingestion.ingestor import ApifyIngestor
    
    # Create sample data
    sample_data = [
        {
            "facebookUrl": "https://www.facebook.com/sahab0769",
            "postId": "test_001",
            "pageName": "sahab0769",
            "url": "https://www.facebook.com/sahab0769/posts/test_001",
            "time": "2026-04-08T02:54:04.000Z",
            "timestamp": 1775616844,
            "user": {
                "id": "100003157204577",
                "name": "আহমেদ সাহাব",
                "profileUrl": "https://www.facebook.com/100003157204577"
            },
            "collaborators": [],
            "text": "গতকাল সরকার নতুন নীতি ঘোষণা করেছে। এটি একটি দীর্ঘ বর্ণনা।",
            "likes": 101,
            "comments": 12,
            "shares": 16,
            "topReactionsCount": 4,
            "media": [
                {
                    "__typename": "Photo",
                    "url": "https://example.com/photo.jpg",
                    "id": "123",
                    "ocrText": "May be an image of text"
                }
            ],
            "feedbackId": "abc123",
            "reactionLikeCount": 88,
            "reactionLoveCount": 11,
            "reactionCareCount": 1,
            "reactionSadCount": 1
        }
    ]
    
    # Create ingestor and manually process
    ingestor = ApifyIngestor(clean_mode=False)
    
    for post_data in sample_data:
        try:
            validated_post, summary = ingestor.validate_post(post_data)
            if summary.is_valid:
                print(f"✅ Post validated: {summary.post_id}")
                print(f"  Language: {summary.detected_language}")
                print(f"  Quality: {summary.quality_score}")
                print(f"  Text length: {summary.text_length}")
                
                # Try to convert to SQLAlchemy model
                post_model = ingestor.convert_to_sqlalchemy_model(validated_post)
                print(f"  Converted to model: {post_model.id}")
            else:
                print(f"❌ Post validation failed: {summary.validation_errors}")
                
        except Exception as e:
            print(f"❌ Error processing post: {e}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Vanta Ingestion Pipeline Tests")
    print("=" * 60)
    print()
    
    test_language_detection()
    test_schemas()
    test_database_connection()
    test_ingestor()
    
    print()
    print("=" * 60)
    print("Tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()