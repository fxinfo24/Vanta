"""
NLP utilities for Vanta
Provides natural language processing functions for text analysis
"""

import re
import string
import logging
from typing import Dict, List, Any, Tuple, Set
from collections import Counter
import warnings

logger = logging.getLogger("Vanta.NLPUtils")

# Try importing optional dependencies
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer

    NLTK_AVAILABLE = True
except ImportError:
    logger.warning("NLTK not available. Some NLP functions will be limited.")
    NLTK_AVAILABLE = False

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    logger.warning("spaCy not available. Using simplified NLP processing.")
    SPACY_AVAILABLE = False

try:
    import textstat

    TEXTSTAT_AVAILABLE = True
except ImportError:
    logger.warning("textstat not available. Readability metrics will be unavailable.")
    TEXTSTAT_AVAILABLE = False

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning(
        "scikit-learn/numpy not available. Advanced text processing will be limited."
    )
    SKLEARN_AVAILABLE = False

# Download required NLTK resources if available
if NLTK_AVAILABLE:
    try:
        nltk.data.find("tokenizers/punkt")
        nltk.data.find("corpora/stopwords")
        nltk.data.find("sentiment/vader_lexicon.zip")
        nltk.data.find("corpora/wordnet")
    except LookupError:
        logger.info("Downloading required NLTK resources")
        nltk.download("punkt")
        nltk.download("stopwords")
        nltk.download("vader_lexicon")
        nltk.download("wordnet")

    # Initialize NLP components
    lemmatizer = WordNetLemmatizer()
    stop_words = set(stopwords.words("english"))
    sia = SentimentIntensityAnalyzer()

# Initialize spaCy if available
nlp = None
if SPACY_AVAILABLE:
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.warning(
            "Spacy model 'en_core_web_sm' not found. Using simplified processing."
        )
        try:
            # Try to use blank model as fallback
            nlp = spacy.blank("en")
        except:
            logger.error("Could not initialize any spaCy model")

# Simple lexicons for trait analysis
# These would ideally be expanded or replaced with more comprehensive lexicons
emotion_lexicon = {
    "happy",
    "sad",
    "angry",
    "excited",
    "love",
    "hate",
    "joy",
    "fear",
    "worry",
    "anxious",
    "surprised",
    "disgusted",
    "proud",
    "ashamed",
    "guilty",
    "grateful",
}

positive_lexicon = {
    "good",
    "great",
    "excellent",
    "wonderful",
    "amazing",
    "fantastic",
    "beautiful",
    "happy",
    "joy",
    "love",
    "best",
    "perfect",
    "awesome",
    "superb",
    "brilliant",
}

negative_lexicon = {
    "bad",
    "terrible",
    "awful",
    "horrible",
    "poor",
    "worst",
    "ugly",
    "hate",
    "sad",
    "angry",
    "worst",
    "stupid",
    "dumb",
    "useless",
    "failure",
}

achievement_lexicon = {
    "achieve",
    "success",
    "win",
    "accomplish",
    "complete",
    "finish",
    "goal",
    "target",
    "objective",
    "triumph",
    "victory",
    "succeed",
    "excel",
    "master",
    "conquer",
}

social_lexicon = {
    "friend",
    "family",
    "party",
    "together",
    "community",
    "social",
    "group",
    "team",
    "people",
    "relationship",
    "connection",
    "join",
    "share",
    "meet",
}

cognitive_lexicon = {
    "think",
    "consider",
    "analyze",
    "evaluate",
    "assess",
    "reason",
    "logic",
    "rational",
    "reflect",
    "ponder",
    "contemplate",
    "deduce",
    "conclude",
    "understand",
    "comprehend",
}


def preprocess_text(text: str) -> str:
    """
    Preprocess text for analysis: lowercase, strip URLs, remove
    punctuation, collapse whitespace.

    Contract (relied on by tests and NLP callers): URLs must not survive
    preprocessing (they skew token/sentiment stats), and punctuation
    , . ! ? must be removed.

    Args:
        text: Input text to preprocess

    Returns:
        Preprocessed text
    """
    if not text:
        return ""

    text = text.lower()

    # Remove URLs (http/https and bare www links)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)

    # Remove punctuation
    text = re.sub(r"[,\.!?]", " ", text)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize_text(text: str) -> List[str]:
    """
    Tokenize text into words

    Args:
        text: Input text

    Returns:
        List of word tokens
    """
    if not text:
        return []

    if NLTK_AVAILABLE:
        return word_tokenize(text)
    else:
        # Simple fallback tokenization
        # Remove punctuation and split by whitespace
        text = text.translate(str.maketrans("", "", string.punctuation))
        return text.split()


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract named entities from text

    Args:
        text: Input text

    Returns:
        Dictionary of entity types and values
    """
    if not text or not SPACY_AVAILABLE or not nlp:
        return {"PERSON": [], "ORG": [], "GPE": [], "DATE": [], "MISC": []}

    try:
        doc = nlp(text)
        entities = {}

        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append(ent.text)

        # Ensure common entity types are always in the result
        for etype in ["PERSON", "ORG", "GPE", "DATE"]:
            if etype not in entities:
                entities[etype] = []

        return entities
    except Exception as e:
        logger.error(f"Error extracting entities: {str(e)}")
        return {"PERSON": [], "ORG": [], "GPE": [], "DATE": [], "MISC": []}


def sentiment_backend() -> str:
    """Which scorer analyze_sentiment uses here: 'vader' or 'lexicon'.

    Production installs the minimal requirements.txt, which has no nltk, so the
    offline word list is what runs on the host - callers must label results
    accordingly instead of claiming VADER.
    """
    return "vader" if NLTK_AVAILABLE else "lexicon"


def analyze_sentiment(text: str) -> Dict[str, float]:
    """
    Analyze sentiment of text

    Args:
        text: Input text

    Returns:
        Dictionary with sentiment scores
    """
    if not text:
        return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}

    if NLTK_AVAILABLE:
        try:
            scores = sia.polarity_scores(text)
            return scores
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {str(e)}")

    # Simple fallback sentiment analysis
    tokens = tokenize_text(text)
    pos_words = sum(1 for word in tokens if word in positive_lexicon)
    neg_words = sum(1 for word in tokens if word in negative_lexicon)

    # Scoring by word-count ratio dilutes a single "great" in a long post to
    # 0.017, so every real post came back neutral (measured: 30 posts, 0
    # non-neutral, and the report showed a flat 100% neutral). VADER saturates
    # on a few strong words; this does too, at three words per unit.
    compound = max(-1.0, min(1.0, (pos_words - neg_words) / 3.0))
    pos_score = compound if compound > 0 else 0.0
    neg_score = -compound if compound < 0 else 0.0
    neu_score = max(1.0 - abs(compound), 0.0)

    return {"pos": pos_score, "neg": neg_score, "neu": neu_score, "compound": compound}


def calculate_readability_metrics(text: str) -> Dict[str, float]:
    """
    Calculate readability metrics for text

    Args:
        text: Input text

    Returns:
        Dictionary with readability scores
    """
    if not text:
        return {
            "flesch_reading_ease": 0.0,
            "flesch_kincaid_grade": 0.0,
            "smog_index": 0.0,
            "coleman_liau_index": 0.0,
            "automated_readability_index": 0.0,
            "dale_chall_readability_score": 0.0,
            "difficult_words": 0,
            "lexicon_count": 0,
            "sentence_count": 0,
        }

    if TEXTSTAT_AVAILABLE:
        try:
            return {
                "flesch_reading_ease": textstat.flesch_reading_ease(text),
                "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
                "smog_index": textstat.smog_index(text),
                "coleman_liau_index": textstat.coleman_liau_index(text),
                "automated_readability_index": textstat.automated_readability_index(
                    text
                ),
                "dale_chall_readability_score": textstat.dale_chall_readability_score(
                    text
                ),
                "difficult_words": textstat.difficult_words(text),
                "lexicon_count": textstat.lexicon_count(text),
                "sentence_count": textstat.sentence_count(text),
            }
        except Exception as e:
            logger.error(f"Error calculating readability metrics: {str(e)}")

    # Simple fallback for some basic metrics
    words = tokenize_text(text)
    sentences = text.split(". ")

    return {
        "flesch_reading_ease": 0.0,  # Placeholder
        "flesch_kincaid_grade": 0.0,  # Placeholder
        "smog_index": 0.0,  # Placeholder
        "coleman_liau_index": 0.0,  # Placeholder
        "automated_readability_index": 0.0,  # Placeholder
        "dale_chall_readability_score": 0.0,  # Placeholder
        "difficult_words": len([w for w in words if len(w) > 6]),
        "lexicon_count": len(words),
        "sentence_count": len(sentences),
    }


def extract_keywords(text: str, top_n: int = 10) -> List[Tuple[str, float]]:
    """
    Extract keywords from text using TF-IDF

    Args:
        text: Input text
        top_n: Number of top keywords to return

    Returns:
        List of (keyword, score) tuples
    """
    if not text:
        return []

    if SKLEARN_AVAILABLE and NLTK_AVAILABLE:
        try:
            # Tokenize and preprocess
            tokens = [w for w in tokenize_text(text) if w not in stop_words]
            processed_text = " ".join(tokens)

            # Use TF-IDF to extract keywords
            vectorizer = TfidfVectorizer(max_features=100)
            tfidf_matrix = vectorizer.fit_transform([processed_text])

            # Get feature names
            feature_names = vectorizer.get_feature_names_out()

            # Get scores
            tfidf_scores = zip(feature_names, tfidf_matrix.toarray()[0])
            sorted_scores = sorted(tfidf_scores, key=lambda x: x[1], reverse=True)

            return sorted_scores[:top_n]
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")

    # Simple fallback using word frequency
    if not text:
        return []

    words = tokenize_text(text)
    if NLTK_AVAILABLE:
        words = [w for w in words if w not in stop_words]
    else:
        # Remove common English stop words
        common_stops = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "if",
            "because",
            "as",
            "what",
            "when",
            "where",
            "how",
            "that",
            "this",
            "these",
            "those",
            "then",
            "to",
            "of",
            "for",
            "with",
            "by",
            "about",
            "against",
            "between",
            "into",
            "through",
        }
        words = [w for w in words if w not in common_stops and len(w) > 1]

    word_freq = Counter(words)
    total_words = len(words)

    # Calculate relative frequency and sort
    word_scores = [
        (word, count / total_words) for word, count in word_freq.most_common(top_n)
    ]

    return word_scores


def analyze_writing_style(text: str) -> Dict[str, Any]:
    """
    Analyze writing style characteristics

    Args:
        text: Input text

    Returns:
        Dictionary with style metrics and indicators
    """
    if not text:
        return {
            "complexity": 0.0,
            "formality": 0.0,
            "emotional_tone": 0.0,
            "vocabulary_diversity": 0.0,
            "average_sentence_length": 0.0,
            "word_count": 0,
        }

    try:
        # Get basic text properties
        if NLTK_AVAILABLE:
            words = word_tokenize(text)
            sentences = sent_tokenize(text)
        else:
            # Simple tokenization fallbacks
            words = text.split()
            sentences = text.split(". ")

        # Only keep actual words
        words = [word for word in words if word.isalnum()]

        if not words or not sentences:
            return {
                "complexity": 0.0,
                "formality": 0.0,
                "emotional_tone": 0.0,
                "vocabulary_diversity": 0.0,
                "average_sentence_length": 0.0,
                "word_count": 0,
            }

        # Calculate basic metrics
        word_count = len(words)
        avg_sentence_length = word_count / len(sentences) if sentences else 0
        # Vocabulary diversity: average of unigram and bigram type-token
        # ratios. Plain unigram TTR (unique/total) is length-biased - it
        # penalises long text, so a rich long passage scored LOWER than a
        # short simple one. Bigram TTR is far more length-robust; averaging
        # the two keeps the 0-1 scale existing consumers expect (>0.8 etc.)
        # while ordering rich vs simple text correctly.
        unigram_ttr = len(set(words)) / word_count if word_count > 0 else 0
        bigrams = list(zip(words, words[1:]))
        bigram_ttr = len(set(bigrams)) / len(bigrams) if bigrams else unigram_ttr
        unique_words_ratio = (unigram_ttr + bigram_ttr) / 2

        # Calculate lexical density and other metrics if spaCy is available
        if SPACY_AVAILABLE and nlp:
            doc = nlp(text)
            pos_counts = Counter([token.pos_ for token in doc])
            total_tokens = len(doc)

            # Calculate lexical density (content words / total words)
            content_pos = ["NOUN", "VERB", "ADJ", "ADV"]
            content_words = sum(pos_counts.get(pos, 0) for pos in content_pos)
            lexical_density = content_words / total_tokens if total_tokens > 0 else 0

            # Count punctuation
            punct_counts = {}
            for char in text:
                if char in string.punctuation:
                    punct_counts[char] = punct_counts.get(char, 0) + 1

            # Normalize punctuation counts
            punct_freq = {p: count / len(text) for p, count in punct_counts.items()}

            # POS distributions
            pos_distribution = {
                pos: count / total_tokens for pos, count in pos_counts.items()
            }

        else:
            # Simple fallbacks
            lexical_density = 0.5  # Default value
            punct_counts = {}
            punct_freq = {}
            pos_distribution = {}

        # Calculate complexity (sentence length + vocabulary diversity).
        # Old formula min(len/20 + diversity, 1.0) saturated at 1.0 for both
        # simple and complex text, destroying the ordering. Weight each
        # component 50/50 so complex text (long sentences, diverse vocab)
        # scores higher than simple text while staying in 0-1.
        complexity = min(
            (min(avg_sentence_length, 20) / 20) * 0.5 + unique_words_ratio * 0.5,
            1.0,
        )

        # Calculate sentiment for emotional tone
        sentiment = analyze_sentiment(text)
        emotional_tone = abs(sentiment["compound"])

        # Calculate formality (more nouns/prepositions and fewer pronouns/adverbs = more formal)
        formality = 0.5  # Default middle value
        if SPACY_AVAILABLE and nlp:
            formality_indicators = [
                pos_distribution.get("NOUN", 0) * 0.25,
                pos_distribution.get("ADP", 0) * 0.25,  # Prepositions
                pos_distribution.get("DET", 0) * 0.15,
                0.5 - (pos_distribution.get("PRON", 0) * 0.25),  # Fewer pronouns
                0.5 - (pos_distribution.get("ADV", 0) * 0.25),  # Fewer adverbs
                0.5 - (punct_freq.get("!", 0) * 10),  # Fewer exclamations
            ]
            formality = min(
                max(sum(formality_indicators) / len(formality_indicators), 0.0), 1.0
            )

        return {
            "complexity": complexity,
            "formality": formality,
            "emotional_tone": emotional_tone,
            "vocabulary_diversity": unique_words_ratio,
            "average_sentence_length": avg_sentence_length,
            "word_count": word_count,
            "lexical_density": lexical_density if SPACY_AVAILABLE else None,
            "punctuation_frequency": punct_freq if SPACY_AVAILABLE else None,
            "pos_distribution": pos_distribution if SPACY_AVAILABLE else None,
        }
    except Exception as e:
        logger.error(f"Error analyzing writing style: {str(e)}")
        return {
            "complexity": 0.0,
            "formality": 0.0,
            "emotional_tone": 0.0,
            "vocabulary_diversity": 0.0,
            "average_sentence_length": 0.0,
            "word_count": 0,
        }


def map_personality_traits(text: str) -> Dict[str, float]:
    """
    Map writing patterns to Big Five personality traits

    Args:
        text: Input text

    Returns:
        Dictionary with personality trait scores (0-1 scale)
    """
    if not text:
        return {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
            "analytical_thinking": 0.5,
        }

    try:
        # Initialize traits with neutral values
        traits = {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
            "analytical_thinking": 0.5,
        }

        # Get text analysis results
        style = analyze_writing_style(text)
        sentiment = analyze_sentiment(text)

        # Get word counts for different lexicons
        words = tokenize_text(text.lower())

        emotion_words = sum(1 for word in words if word in emotion_lexicon)
        positive_words = sum(1 for word in words if word in positive_lexicon)
        negative_words = sum(1 for word in words if word in negative_lexicon)
        complex_words = sum(1 for word in words if len(word) > 6)
        achievement_words = sum(1 for word in words if word in achievement_lexicon)
        social_words = sum(1 for word in words if word in social_lexicon)
        cognitive_words = sum(1 for word in words if word in cognitive_lexicon)

        # Word count for normalization
        word_count = len([w for w in words if len(w) > 0])
        if word_count == 0:
            return traits  # Return neutral values if no words

        # Apply rules for each trait

        # Openness
        openness_indicators = [
            style["lexical_density"] * 0.3 if "lexical_density" in style else 0.15,
            style["vocabulary_diversity"] * 0.4,  # Varied vocabulary indicates openness
            min(complex_words / word_count * 3, 0.3),  # Complex words suggest openness
            sentiment["compound"] * 0.1 + 0.05,  # Slight boost for positive sentiment
        ]
        traits["openness"] = min(max(sum(openness_indicators), 0.0), 1.0)

        # Conscientiousness
        if "pos_distribution" in style:
            pos_dist = style["pos_distribution"]
            conscientious_indicators = [
                min(
                    pos_dist.get("NOUN", 0) * 1.2, 0.3
                ),  # Nouns suggest detail orientation
                min(achievement_words / word_count * 4, 0.3),  # Achievement words
                (1 - (style.get("punctuation_frequency", {}).get("...", 0) * 10)) * 0.2,
                min(cognitive_words / word_count * 3, 0.2),  # Analytical words
            ]
            traits["conscientiousness"] = min(
                max(sum(conscientious_indicators), 0.0), 1.0
            )

        # Extraversion
        extraversion_indicators = [
            min(social_words / word_count * 4, 0.4),  # Social reference words
            sentiment["pos"] * 0.3,  # Positive emotion correlates with extraversion
            (
                (style.get("punctuation_frequency", {}).get("!", 0) * 5) * 0.15
                if "punctuation_frequency" in style
                else 0
            ),
            min(emotion_words / word_count * 2, 0.15),  # Emotional expression
        ]
        traits["extraversion"] = min(max(sum(extraversion_indicators), 0.0), 1.0)

        # Agreeableness
        agreeableness_indicators = [
            min(
                positive_words / word_count * 3, 0.4
            ),  # Positive words correlate with agreeableness
            (0.5 - min(negative_words / word_count * 4, 0.5))
            * 0.3,  # Fewer negative words
            sentiment["pos"] * 0.3,  # Positive sentiment
        ]
        traits["agreeableness"] = min(max(sum(agreeableness_indicators), 0.0), 1.0)

        # Neuroticism
        neuroticism_indicators = [
            min(negative_words / word_count * 3, 0.4),  # Negative words
            (0.5 - sentiment["compound"]) * 0.3,  # Negative sentiment
            min(words.count("i") / word_count * 8, 0.3),  # Self-reference
        ]
        traits["neuroticism"] = min(max(sum(neuroticism_indicators), 0.0), 1.0)

        # Analytical thinking
        analytical_indicators = [
            style["complexity"] * 0.4,  # Text complexity
            min(cognitive_words / word_count * 5, 0.4),  # Cognitive process words
            style["formality"]
            * 0.2,  # Formal language correlates with analytical thinking
        ]
        traits["analytical_thinking"] = min(max(sum(analytical_indicators), 0.0), 1.0)

        return traits
    except Exception as e:
        logger.error(f"Error mapping personality traits: {str(e)}")
        return {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
            "analytical_thinking": 0.5,
        }


def generate_style_fingerprint(text: str) -> Dict[str, Any]:
    """
    Generate a stylistic fingerprint for writing style comparison

    Args:
        text: Input text

    Returns:
        Dictionary with style fingerprint data
    """
    if not text:
        return {
            "hash": "insufficient_data",
            "signature_features": [],
            "confidence": 0.0,
        }

    try:
        # Extract features for the fingerprint
        style = analyze_writing_style(text)

        # Create feature vector from style metrics
        features = {
            "avg_sent_len": style["average_sentence_length"],
            "vocab_diversity": style["vocabulary_diversity"],
            "complexity": style["complexity"],
            "formality": style["formality"],
            "emotional_tone": style["emotional_tone"],
        }

        # Add POS distribution if available
        if "pos_distribution" in style and style["pos_distribution"]:
            for pos, value in style["pos_distribution"].items():
                features[f"pos_{pos}"] = value

        # Add punctuation frequencies if available
        if "punctuation_frequency" in style and style["punctuation_frequency"]:
            for punct, freq in style["punctuation_frequency"].items():
                if punct in ",.!?;:":  # Only include common punctuation
                    features[f"punct_{punct}"] = freq

        # Generate simple hash from major features
        hash_components = [
            f"{k[:2]}{v:.6f}"
            for k, v in sorted(features.items())
            if k in ["avg_sent_len", "vocab_diversity", "complexity", "formality"]
        ]
        style_hash = "-".join(hash_components)

        # Identify signature features (the most distinctive elements)
        signature_features = []

        if style["average_sentence_length"] > 25:
            signature_features.append("Very long sentences")
        elif style["average_sentence_length"] < 10:
            signature_features.append("Very short sentences")

        if style["vocabulary_diversity"] > 0.8:
            signature_features.append("Exceptionally diverse vocabulary")
        elif style["vocabulary_diversity"] < 0.3:
            signature_features.append("Limited vocabulary range")

        if "punctuation_frequency" in style:
            punct_freq = style["punctuation_frequency"]
            if punct_freq.get("!", 0) > 0.01:
                signature_features.append("Frequent exclamation marks")
            if punct_freq.get("?", 0) > 0.01:
                signature_features.append("Frequent questions")
            if punct_freq.get(";", 0) > 0.005:
                signature_features.append("Semicolon usage")
            if punct_freq.get("...", 0) > 0.002:
                signature_features.append("Ellipsis usage")

        # Determine confidence based on text length
        confidence = min(len(text) / 1000, 1.0)  # More text = higher confidence

        return {
            "hash": style_hash,
            "features": features,
            "signature_features": signature_features,
            "confidence": confidence,
        }
    except Exception as e:
        logger.error(f"Error generating style fingerprint: {str(e)}")
        return {"hash": "error", "signature_features": [], "confidence": 0.0}


# Add the extract_topics function
def extract_topics(text: str, num_topics: int = 5) -> List[Dict[str, Any]]:
    """
    Extract main topics from text

    Args:
        text: Input text
        num_topics: Number of topics to extract

    Returns:
        List of topic dictionaries with name and relevance score
    """
    if not text:
        return []

    try:
        # Extract keywords first
        keywords = extract_keywords(text, top_n=20)

        # Group keywords into topics using basic clustering
        # (In a real implementation, this would use more sophisticated topic modeling)
        topics = []

        if not keywords:
            return []

        # Simple topic extraction using keyword frequency and relevance
        seen_words = set()
        for keyword, score in keywords:
            # Skip if we already used this word or if it's too short
            if keyword in seen_words or len(keyword) < 3:
                continue

            # Create a simple topic
            if len(topics) < num_topics:
                topic = {
                    "name": keyword.capitalize(),
                    "score": float(score),
                    "keywords": [keyword],
                }
                topics.append(topic)
                seen_words.add(keyword)

        # Sort topics by score
        topics.sort(key=lambda x: x["score"], reverse=True)

        return topics[:num_topics]
    except Exception as e:
        logger.error(f"Error extracting topics: {str(e)}")
        return []
