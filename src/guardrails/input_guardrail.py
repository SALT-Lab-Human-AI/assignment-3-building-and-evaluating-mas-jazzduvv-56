"""
Input Guardrail
Checks user inputs for safety violations using Guardrails AI framework.
"""

from typing import Dict, Any, List
import logging


class InputGuardrail:
    """
    Guardrail for checking input safety.
    
    Uses Guardrails AI framework for validation with custom rules.
    Checks for:
    - Query length constraints
    - Toxic/harmful language
    - Prompt injection attempts
    - Topic relevance
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize input guardrail.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("guardrails.input")
        
        # Load safety configuration
        safety_config = config.get("safety", {})
        self.enabled = safety_config.get("enabled", True)
        self.prohibited_categories = safety_config.get("prohibited_categories", [])
        
        # Initialize Guardrails AI
        try:
            from guardrails import Guard
            from guardrails.hub import ToxicLanguage, RestrictToTopic
            
            # Create guard with validators
            self.guard = Guard()
            
            # Add length validator (10-2000 characters)
            self.guard = self.guard.use(
                ToxicLanguage(
                    threshold=0.5,
                    validation_method="sentence",
                    on_fail="exception"
                ),
                on="prompt"
            )
            
            # Add topic restriction if configured
            system_topic = config.get("system", {}).get("topic", "")
            if system_topic:
                self.guard = self.guard.use(
                    RestrictToTopic(
                        valid_topics=[system_topic, "research", "academic"],
                        invalid_topics=["medical advice", "legal advice", "financial advice"],
                        on_fail="exception"
                    ),
                    on="prompt"
                )
            
            self.guardrails_available = True
            self.logger.info("Guardrails AI initialized successfully")
            
        except ImportError:
            self.logger.warning("Guardrails AI not available, using fallback validation")
            self.guard = None
            self.guardrails_available = False
        except Exception as e:
            self.logger.error(f"Error initializing Guardrails AI: {e}")
            self.guard = None
            self.guardrails_available = False

    def validate(self, query: str) -> Dict[str, Any]:
        """
        Validate input query.

        Args:
            query: User input to validate

        Returns:
            Validation result with valid flag, violations list, and sanitized input
        """
        if not self.enabled:
            return {
                "valid": True,
                "violations": [],
                "sanitized_input": query
            }
        
        violations = []
        
        # Basic length check (always applied)
        if len(query) < 5:
            violations.append({
                "validator": "length",
                "reason": "Query too short (minimum 5 characters)",
                "severity": "low"
            })
        
        if len(query) > 2000:
            violations.append({
                "validator": "length",
                "reason": "Query too long (maximum 2000 characters)",
                "severity": "medium"
            })
        
        # Prompt injection check
        injection_violations = self._check_prompt_injection(query)
        violations.extend(injection_violations)
        
        # Use Guardrails AI if available
        if self.guardrails_available and self.guard:
            try:
                result = self.guard.validate(query)
                
                # Check if validation passed
                if not result.validation_passed:
                    for error in result.error_spans_in_output:
                        violations.append({
                            "validator": "guardrails_ai",
                            "reason": str(error),
                            "severity": "high"
                        })
            except Exception as e:
                self.logger.warning(f"Guardrails AI validation failed: {e}")
                # Fall back to basic checks
                toxic_violations = self._check_toxic_language(query)
                violations.extend(toxic_violations)
        else:
            # Fallback validation without Guardrails AI
            toxic_violations = self._check_toxic_language(query)
            violations.extend(toxic_violations)
            
            relevance_violations = self._check_relevance(query)
            violations.extend(relevance_violations)
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "sanitized_input": query  # Could implement sanitization if needed
        }

    def _check_toxic_language(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for toxic/harmful language using keyword matching.
        
        This is a basic fallback when Guardrails AI is not available.
        In production, use proper toxicity models.
        """
        violations = []
        
        # Basic toxic keyword list (expandable)
        toxic_keywords = [
            "violent", "kill", "harm", "attack", "abuse",
            "hate", "racist", "sexist", "offensive",
            # Malicious cyber activity keywords
            "create virus", "create malware", "create ransomware",
            "hack into", "exploit vulnerability", "ddos attack",
            "create trojan", "create worm", "create spyware",
            "bypass security", "crack password", "steal data"
        ]
        
        text_lower = text.lower()
        found_keywords = [kw for kw in toxic_keywords if kw in text_lower]
        
        if found_keywords:
            violations.append({
                "validator": "toxic_language",
                "reason": f"Contains potentially toxic language: {', '.join(found_keywords)}",
                "severity": "high"
            })
        
        return violations

    def _check_prompt_injection(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for prompt injection attempts.

        TODO: YOUR CODE HERE Implement prompt injection detection
        """
        violations = []
        # Check for common prompt injection patterns
        injection_patterns = [
            "ignore previous",
            "ignore all previous",
            "disregard",
            "forget everything",
            "new instructions",
            "system prompt",
            "you are now"
        ]
        
        text_lower = text.lower()
        found_patterns = [p for p in injection_patterns if p in text_lower]
        
        if found_patterns:
            violations.append({
                "validator": "prompt_injection",
                "reason": f"Potential prompt injection detected: {', '.join(found_patterns)}",
                "severity": "high"
            })
        
        return violations

    def _check_relevance(self, query: str) -> List[Dict[str, Any]]:
        """
        Check if query is relevant to the system's configured topic.
        
        Basic keyword-based relevance check. In production, use semantic similarity.
        """
        violations = []
        
        # Get configured topic from config
        system_topic = self.config.get("system", {}).get("topic", "").lower()
        
        if not system_topic:
            # No topic restriction configured
            return violations
        
        # Check for prohibited off-topic patterns
        off_topic_patterns = [
            "what's the weather",
            "weather today",
            "tell me a joke",
            "tell me a funny",
            "tell me something funny",
            "make me laugh",
            "play a game",
            "write a poem",
            "write me a poem",
            "solve this math",
            "solve math",
            "calculate",
            "recipe",
            "cooking",
            "virus",  # Block any mention of creating viruses
            "malware",
            "ransomware",
            "trojan",
            "worm",
            "spyware",
            "hack into",
            "hack a",
            "exploit",
            "ddos",
            "crack password",
            "bypass security",
        ]
        
        # Malicious intent patterns (multi-word)
        malicious_patterns = [
            "how to create",
            "how to make",
            "how to build",
            "steps to create",
            "guide to creating",
        ]
        
        query_lower = query.lower()
        
        # Check for malicious combinations
        has_malicious_intent = any(pattern in query_lower for pattern in malicious_patterns)
        has_harmful_target = any(pattern in query_lower for pattern in ["virus", "malware", "ransomware", "trojan", "worm", "exploit"])
        
        if has_malicious_intent and has_harmful_target:
            violations.append({
                "validator": "relevance",
                "reason": f"Query requests malicious content that is not related to {system_topic} research",
                "severity": "high"
            })
            return violations
        
        query_lower = query.lower()
        
        # First check explicit off-topic patterns
        for pattern in off_topic_patterns:
            if pattern in query_lower:
                violations.append({
                    "validator": "relevance",
                    "reason": f"Query appears off-topic for {system_topic} research",
                    "severity": "high"
                })
                return violations
        
        # Check if query is actually about the research topic
        # For "AI-Generated Synthetic Realities", look for relevant keywords
        topic_keywords = [
            "synthetic", "ai", "artificial intelligence", "generative",
            "virtual", "simulation", "reality", "world", "environment",
            "immersive", "3d", "unreal", "unity", "metaverse",
            "procedural generation", "neural rendering", "human-ai",
            "co-creation", "collaboration"
        ]
        
        # If query is longer than 10 words, check for at least one topic keyword
        if len(query_lower.split()) > 10:
            has_topic_keyword = any(keyword in query_lower for keyword in topic_keywords)
            if not has_topic_keyword:
                violations.append({
                    "validator": "relevance",
                    "reason": f"Query does not appear related to {system_topic}. Please ask about AI-generated synthetic worlds, virtual environments, or human-AI co-creation.",
                    "severity": "medium"
                })
        
        return violations
