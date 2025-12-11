"""
Safety Manager
Coordinates safety guardrails and logs safety events.
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import json


class SafetyManager:
    """
    Manages safety guardrails for the multi-agent system.

    TODO: YOUR CODE HERE
    - Integrate with Guardrails AI or NeMo Guardrails
    - Define safety policies
    - Implement logging of safety events
    - Handle different violation types with appropriate responses
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize safety manager.

        Args:
            config: Safety configuration from config.yaml
        """
        # Extract safety configuration
        safety_config = config.get("safety", {})
        
        self.config = safety_config
        self.enabled = safety_config.get("enabled", True)
        self.log_events = safety_config.get("log_events", True)
        self.logger = logging.getLogger("safety")

        # Safety event log
        self.safety_events: List[Dict[str, Any]] = []

        # Prohibited categories
        self.prohibited_categories = safety_config.get("prohibited_categories", [
            "harmful_content",
            "personal_attacks",
            "misinformation",
            "off_topic_queries"
        ])

        # Violation response strategy
        self.on_violation = safety_config.get("on_violation", {})

        # Initialize input and output guardrails
        try:
            from .input_guardrail import InputGuardrail
            from .output_guardrail import OutputGuardrail
            
            self.input_guardrail = InputGuardrail(config)
            self.output_guardrail = OutputGuardrail(config)
            
            self.logger.info("Safety guardrails initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing guardrails: {e}")
            self.input_guardrail = None
            self.output_guardrail = None

    def check_input_safety(self, query: str) -> Dict[str, Any]:
        """
        Check if input query is safe to process using InputGuardrail.

        Args:
            query: User query to check

        Returns:
            Dictionary with 'safe' boolean, 'violations' list, and optional 'sanitized_query'
        """
        if not self.enabled:
            return {"safe": True, "violations": []}

        # Use InputGuardrail if available
        if self.input_guardrail:
            try:
                result = self.input_guardrail.validate(query)
                
                is_safe = result.get("valid", True)
                violations = result.get("violations", [])
                sanitized_query = result.get("sanitized_input", query)
                
                # Log safety event if violations found
                if not is_safe and self.log_events:
                    self._log_safety_event(
                        event_type="input_violation",
                        content=query,
                        violations=violations,
                        is_safe=is_safe
                    )
                
                return {
                    "safe": is_safe,
                    "violations": violations,
                    "sanitized_query": sanitized_query
                }
                
            except Exception as e:
                self.logger.error(f"Error checking input safety: {e}")
                return {"safe": True, "violations": [], "error": str(e)}
        else:
            # Fallback if guardrail not initialized
            self.logger.warning("Input guardrail not available, allowing query")
            return {"safe": True, "violations": []}

        is_safe = len(violations) == 0

        # Log safety event
        if not is_safe and self.log_events:
            self._log_safety_event("input", query, violations, is_safe)

        return {
            "safe": is_safe,
            "violations": violations
        }

    def check_output_safety(
        self,
        response: str,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Check if output response is safe to return using OutputGuardrail.

        Args:
            response: Generated response to check
            sources: Optional list of sources used for fact-checking

        Returns:
            Dictionary with 'safe' boolean, 'violations' list, and 'response'
        """
        if not self.enabled:
            return {"safe": True, "response": response}

        # Use OutputGuardrail if available
        if self.output_guardrail:
            try:
                result = self.output_guardrail.validate(response, sources)
                
                is_safe = result.get("valid", True)
                violations = result.get("violations", [])
                sanitized_response = result.get("sanitized_output", response)
                
                # Log safety event if violations found
                if not is_safe and self.log_events:
                    self._log_safety_event(
                        event_type="output_violation",
                        content=response[:200],  # Log first 200 chars
                        violations=violations,
                        is_safe=is_safe
                    )
                
                # Prepare result
                result_dict = {
                    "safe": is_safe,
                    "violations": violations,
                    "response": response
                }
                
                # Apply sanitization if needed
                if not is_safe:
                    action = self.on_violation.get("action", "refuse")
                    if action == "sanitize":
                        result_dict["response"] = sanitized_response
                    elif action == "refuse":
                        result_dict["response"] = self.on_violation.get(
                            "message",
                            "I cannot provide this response due to safety policies."
                        )
                
                return result_dict
                
            except Exception as e:
                self.logger.error(f"Error checking output safety: {e}")
                return {"safe": True, "violations": [], "response": response, "error": str(e)}
        else:
            # Fallback if guardrail not initialized
            self.logger.warning("Output guardrail not available, allowing response")
            return {"safe": True, "violations": [], "response": response}

    def _sanitize_response(self, response: str, violations: List[Dict[str, Any]]) -> str:
        """
        Sanitize response by removing or redacting unsafe content.
        
        This is now handled by OutputGuardrail, but kept for backward compatibility.
        """
        if self.output_guardrail:
            # Use guardrail's sanitization
            result = self.output_guardrail.validate(response)
            return result.get("sanitized_output", response)
        else:
            # Fallback: basic redaction
            return "[CONTENT SANITIZED FOR SAFETY] " + response

    def _log_safety_event(
        self,
        event_type: str,
        content: str,
        violations: List[Dict[str, Any]],
        is_safe: bool
    ):
        """
        Log a safety event.

        Args:
            event_type: "input" or "output"
            content: The content that was checked
            violations: List of violations found
            is_safe: Whether content passed safety checks
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "safe": is_safe,
            "violations": violations,
            "content_preview": content[:100] + "..." if len(content) > 100 else content
        }

        self.safety_events.append(event)
        self.logger.warning(f"Safety event: {event_type} - safe={is_safe}")

        # Write to safety log file if configured
        log_file = self.config.get("safety_log_file")
        if log_file and self.log_events:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                self.logger.error(f"Failed to write safety log: {e}")

    def get_safety_events(self) -> List[Dict[str, Any]]:
        """Get all logged safety events."""
        return self.safety_events

    def get_safety_stats(self) -> Dict[str, Any]:
        """
        Get statistics about safety events.

        Returns:
            Dictionary with safety statistics
        """
        total = len(self.safety_events)
        input_events = sum(1 for e in self.safety_events if e["type"] == "input")
        output_events = sum(1 for e in self.safety_events if e["type"] == "output")
        violations = sum(1 for e in self.safety_events if not e["safe"])

        return {
            "total_events": total,
            "input_checks": input_events,
            "output_checks": output_events,
            "violations": violations,
            "violation_rate": violations / total if total > 0 else 0
        }

    def clear_events(self):
        """Clear safety event log."""
        self.safety_events = []
