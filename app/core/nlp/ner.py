"""
Vanta: NLP Named Entity Recognition (Layer 3 Enhancement)
spaCy NER for Bengali and English entity extraction
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger("Vanta.NLP.NER")


class NERExtractor:
    """
    Named Entity Recognition using spaCy
    """
    
    def __init__(self):
        self.models = {}
        
    def load_model(self, language: str):
        """
        Load spaCy model for language
        
        For Bengali, we use multilingual model
        For English, use en_core_web_sm
        """
        try:
            if language == "bn":
                # Use multilingual model for Bengali
                import spacy
                self.models["bn"] = spacy.load("xx_ent_wiki_sm")  # Multilingual
            elif language == "en":
                import spacy
                self.models["en"] = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.warning(f"Failed to load spaCy model for {language}: {e}")
            return False
        
        return True
    
    def extract_entities(self, text: str, language: str = "en") -> List[Dict[str, Any]]:
        """
        Extract named entities from text
        """
        if language not in self.models:
            if not self.load_model(language):
                return []
        
        try:
            doc = self.models[language](text)
            
            entities = []
            for ent in doc.ents:
                entity = {
                    "text": ent.text,
                    "type": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 0.8  # Default confidence
                }
                
                # Map spaCy types to our types
                type_mapping = {
                    "PERSON": "PERSON",
                    "ORG": "ORGANIZATION",
                    "GPE": "LOCATION",
                    "LOC": "LOCATION",
                    "DATE": "DATE",
                    "TIME": "TIME",
                    "MONEY": "MONEY",
                    "PERCENT": "PERCENT",
                    "QUANTITY": "QUANTITY"
                }
                
                if entity["type"] in type_mapping:
                    entity["type"] = type_mapping[entity["type"]]
                
                entities.append(entity)
            
            return entities
            
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return []
    
    def extract_entities_batch(self, texts: List[str], language: str = "en") -> List[List[Dict[str, Any]]]:
        """
        Extract entities from batch of texts
        """
        results = []
        for text in texts:
            results.append(self.extract_entities(text, language))
        
        return results


def create_ner_extractor() -> NERExtractor:
    """
    Factory function for NER extractor
    """
    return NERExtractor()