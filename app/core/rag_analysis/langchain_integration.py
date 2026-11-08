"""
Vanta: LangChain Integration (Layer 6 Enhancement)
LangChain for better RAG orchestration and LLM management
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("Vanta.LangChain")


@dataclass
class LangChainConfig:
    """Configuration for LangChain integration"""
    llm_provider: str = "openai"  # openai, anthropic, openrouter
    model_name: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 1000
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 5


class LangChainRAG:
    """
    LangChain-powered RAG system with better orchestration
    
    Features:
    - Document chunking with overlap
    - Vector store integration
    - Better retrieval
    - LLM chain management
    """
    
    def __init__(self, config: Optional[LangChainConfig] = None):
        self.config = config or LangChainConfig()
        self.vector_store = None
        self.llm = None
        self.retriever = None
        
    def initialize(self):
        """Initialize LangChain components"""
        try:
            self._setup_llm()
            self._setup_text_splitter()
            logger.info("LangChain RAG initialized")
            return True
        except Exception as e:
            logger.error(f"LangChain initialization failed: {e}")
            return False
    
    def _setup_llm(self):
        """Setup LLM based on provider"""
        if self.config.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model=self.config.model_name,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        elif self.config.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(
                model=self.config.model_name,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        else:
            # Default to OpenAI
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
    
    def _setup_text_splitter(self):
        """Setup text splitter for document chunking"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""]
        )
    
    def create_vector_store(self, documents: List[str]):
        """
        Create vector store from documents
        
        Returns vector store retriever
        """
        try:
            from langchain_community.embeddings import OpenAIEmbeddings
            from langchain_community.vectorstores import Chroma
            
            # Split documents
            texts = self.text_splitter.split_text("\n\n".join(documents))
            
            # Create embeddings
            embeddings = OpenAIEmbeddings()
            
            # Create vector store
            self.vector_store = Chroma.from_texts(
                texts=texts,
                embedding=embeddings,
                metadatas=[{"source": f"doc_{i}"} for i in range(len(texts))]
            )
            
            # Create retriever
            self.retriever = self.vector_store.as_retriever(
                search_kwargs={"k": self.config.retrieval_top_k}
            )
            
            logger.info(f"Created vector store with {len(texts)} chunks")
            return self.retriever
            
        except Exception as e:
            logger.error(f"Vector store creation failed: {e}")
            return None
    
    def analyze_claim_with_rag(self, claim: str, evidence_documents: List[str]) -> Dict[str, Any]:
        """
        Analyze claim using LangChain RAG pipeline
        """
        if not self.llm:
            self.initialize()
        
        try:
            # Create vector store from evidence
            retriever = self.create_vector_store(evidence_documents)
            
            if not retriever:
                return {
                    "error": "Failed to create vector store",
                    "verdict": "UNVERIFIABLE",
                    "confidence": 0.0
                }
            
            # Create RAG chain
            from langchain.chains import RetrievalQA
            from langchain.prompts import PromptTemplate
            
            # Custom prompt for fact-checking
            prompt_template = """You are a fact-checking analyst. Analyze the claim based ONLY on the provided evidence.

Claim: {claim}

Evidence: {context}

STRICT RULES:
1. ONLY use information from the provided evidence
2. You MUST cite evidence sources for every statement
3. If evidence is insufficient, state "INSUFFICIENT EVIDENCE"
4. Do NOT add information not present in the evidence
5. Do NOT use prior knowledge

VERDICT OPTIONS:
- VERIFIED_TRUE: Clear evidence supports the claim
- VERIFIED_FALSE: Clear evidence contradicts the claim
- MISLEADING: Claim has some truth but is misleading
- UNVERIFIABLE: Insufficient evidence to verify
- DISPUTED: Evidence is contradictory

RESPONSE FORMAT:
Verdict: [VERDICT]
Confidence: [0.0-1.0]
Reasoning: [Detailed reasoning with citations]
Citations: [List of evidence sources cited]
"""
            
            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["claim", "context"]
            )
            
            # Create RAG chain
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                chain_type_kwargs={"prompt": prompt},
                return_source_documents=True
            )
            
            # Run analysis
            result = qa_chain.invoke({"query": claim})
            
            # Parse result
            response_text = result["result"]
            source_documents = result.get("source_documents", [])
            
            # Parse verdict from response
            verdict = self._parse_verdict(response_text)
            confidence = self._parse_confidence(response_text)
            
            return {
                "verdict": verdict,
                "confidence": confidence,
                "reasoning": response_text,
                "citations": [doc.page_content[:200] for doc in source_documents],
                "source_count": len(source_documents),
                "model": self.config.model_name,
                "provider": self.config.llm_provider
            }
            
        except Exception as e:
            logger.error(f"LangChain RAG analysis failed: {e}")
            return {
                "error": str(e),
                "verdict": "UNVERIFIABLE",
                "confidence": 0.0
            }
    
    def _parse_verdict(self, response: str) -> str:
        """Parse verdict from LLM response"""
        lines = response.split("\n")
        for line in lines:
            if line.startswith("Verdict:"):
                return line.replace("Verdict:", "").strip()
        return "UNVERIFIABLE"
    
    def _parse_confidence(self, response: str) -> float:
        """Parse confidence score from LLM response"""
        lines = response.split("\n")
        for line in lines:
            if line.startswith("Confidence:"):
                try:
                    return float(line.replace("Confidence:", "").strip())
                except:
                    pass
        return 0.0
    
    def batch_analyze(self, claims: List[str], evidence_documents: List[str]) -> List[Dict[str, Any]]:
        """
        Batch analyze multiple claims
        """
        results = []
        for claim in claims:
            result = self.analyze_claim_with_rag(claim, evidence_documents)
            results.append(result)
        
        return results


def create_langchain_rag(config: Optional[LangChainConfig] = None) -> LangChainRAG:
    """
    Factory function for LangChain RAG
    """
    return LangChainRAG(config)