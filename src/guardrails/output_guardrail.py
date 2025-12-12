"""
Output Guardrail
Checks system outputs for safety violations.
"""

from typing import Dict, Any, List
import re
import logging


class OutputGuardrail:
    """
    Guardrail for checking output safety.

    TODO: YOUR CODE HERE
    - Integrate with Guardrails AI or NeMo Guardrails
    - Check for harmful content in responses
    - Verify factual consistency
    - Detect potential misinformation
    - Remove PII (personal identifiable information)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize output guardrail.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("guardrails.output")
        
        # Load safety configuration
        safety_config = config.get("safety", {})
        self.enabled = safety_config.get("enabled", True)
        self.prohibited_categories = safety_config.get("prohibited_categories", [])
        
        # Initialize Guardrails AI
        try:
            from guardrails import Guard
            from guardrails.hub import ToxicLanguage, DetectPII
            
            # Create guard with validators
            self.guard = Guard()
            
            # Add toxic language detector
            self.guard = self.guard.use(
                ToxicLanguage(
                    threshold=0.5,
                    validation_method="sentence",
                    on_fail="exception"
                ),
                on="output"
            )
            
            # Add PII detector
            self.guard = self.guard.use(
                DetectPII(
                    pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "SSN", "CREDIT_CARD"],
                    on_fail="exception"
                ),
                on="output"
            )
            
            self.guardrails_available = True
            self.logger.info("Output Guardrails AI initialized successfully")
            
        except ImportError:
            self.logger.warning("Guardrails AI not available, using fallback validation")
            self.guard = None
            self.guardrails_available = False
        except Exception as e:
            self.logger.error(f"Error initializing Guardrails AI: {e}")
            self.guard = None
            self.guardrails_available = False

    def validate(self, response: str, sources: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate output response.

        Args:
            response: Generated response to validate
            sources: Optional list of sources used (for fact-checking)

        Returns:
            Validation result with valid flag, violations list, and sanitized output
        """
        if not self.enabled:
            return {
                "valid": True,
                "violations": [],
                "sanitized_output": response
            }
        
        violations = []
        
        # Use Guardrails AI if available
        if self.guardrails_available and self.guard:
            try:
                result = self.guard.validate(response)
                
                # Check if validation passed
                if not result.validation_passed:
                    for error in result.error_spans_in_output:
                        violations.append({
                            "validator": "guardrails_ai",
                            "reason": str(error),
                            "severity": "high"
                        })
                        
            except Exception as e:
                self.logger.warning(f"Guardrails AI validation error: {e}")
                # Fall back to basic checks
                pii_violations = self._check_pii(response)
                violations.extend(pii_violations)
                
                harmful_violations = self._check_harmful_content(response)
                violations.extend(harmful_violations)
        else:
            # Fallback validation without Guardrails AI
            pii_violations = self._check_pii(response)
            violations.extend(pii_violations)
            
            harmful_violations = self._check_harmful_content(response)
            violations.extend(harmful_violations)
        
        # Check for bias (always applied)
        bias_violations = self._check_bias(response)
        violations.extend(bias_violations)
        
        # Check factual consistency if sources provided
        if sources:
            consistency_violations = self._check_factual_consistency(response, sources)
            violations.extend(consistency_violations)
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "sanitized_output": self._sanitize(response, violations) if violations else response
        }

    def _check_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for personally identifiable information.

        TODO: YOUR CODE HERE Implement comprehensive PII detection
        """
        violations = []

        # Simple regex patterns for common PII
        # Note: Phone pattern requires spaces or dashes to avoid false positives with DOIs/URLs
        patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'(?<!/)(?<!\.)\b\d{3}[-\s]\d{3}[-\s]\d{4}\b(?!/)',  # Requires space or dash between groups
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        }

        for pii_type, pattern in patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                violations.append({
                    "validator": "pii",
                    "pii_type": pii_type,
                    "reason": f"Contains {pii_type}",
                    "severity": "high",
                    "matches": matches
                })

        return violations

    def _check_harmful_content(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for harmful or inappropriate content using keyword matching.
        
        This is a basic fallback when Guardrails AI is not available.
        In production, use proper toxicity models like Perspective API.
        """
        violations = []
        
        # Prohibited content categories from config
        harmful_patterns = {
            "violent": ["kill", "murder", "violence", "attack", "assault"],
            "hateful": ["hate", "racist", "sexist", "discrimination"],
            "dangerous": ["bomb", "weapon", "suicide", "self-harm"],
            "inappropriate": ["explicit", "pornographic", "sexual"]
        }
        
        text_lower = text.lower()
        
        for category, keywords in harmful_patterns.items():
            if category in self.prohibited_categories or not self.prohibited_categories:
                found = [kw for kw in keywords if kw in text_lower]
                if found:
                    violations.append({
                        "validator": "harmful_content",
                        "category": category,
                        "reason": f"Contains potentially {category} content: {', '.join(found)}",
                        "severity": "high"
                    })
        
        return violations

    def _check_factual_consistency(
        self,
        response: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check if response is consistent with sources.
        
        Basic implementation checking for citations and source mentions.
        Advanced implementation would use LLM-based fact verification.
        """
        violations = []
        
        if not sources:
            # No sources to check against
            return violations
        
        # Check if response includes citations
        has_citations = "[" in response and "]" in response
        has_references = "reference" in response.lower() or "source" in response.lower()
        
        if not has_citations and not has_references:
            violations.append({
                "validator": "factual_consistency",
                "reason": "Response does not cite sources",
                "severity": "medium"
            })
        
        # Check for common indicators of fabrication
        fabrication_indicators = [
            "i think", "i believe", "probably", "maybe", "might be",
            "not sure", "unclear", "uncertain"
        ]
        
        text_lower = response.lower()
        found_indicators = [ind for ind in fabrication_indicators if ind in text_lower]
        
        if found_indicators:
            violations.append({
                "validator": "factual_consistency",
                "reason": f"Response contains uncertainty indicators: {', '.join(found_indicators)}",
                "severity": "low"
            })
        
        return violations

    def _check_bias(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for biased or non-inclusive language.
        
        Basic keyword-based approach. In production, use bias detection models.
        """
        violations = []
        
        # Biased terms to flag
        biased_terms = {
            "gender": ["mankind", "manpower", "he/she"],
            "ageism": ["elderly", "old people", "young people"],
            "ableism": ["crazy", "insane", "lame", "blind to"],
        }
        
        text_lower = text.lower()
        
        for bias_type, terms in biased_terms.items():
            found = [term for term in terms if term in text_lower]
            if found:
                violations.append({
                    "validator": "bias_detection",
                    "bias_type": bias_type,
                    "reason": f"Contains potentially biased language ({bias_type}): {', '.join(found)}",
                    "severity": "low"
                })
        
        return violations

    def _sanitize(self, text: str, violations: List[Dict[str, Any]]) -> str:
        """
        Sanitize text by removing/redacting violations.

        TODO: YOUR CODE HERE Implement sanitization logic
        """
        sanitized = text

        # Redact PII
        for violation in violations:
            if violation.get("validator") == "pii":
                for match in violation.get("matches", []):
                    sanitized = sanitized.replace(match, "[REDACTED]")

        return sanitized
