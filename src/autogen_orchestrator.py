"""
AutoGen-Based Orchestrator

This orchestrator uses AutoGen's RoundRobinGroupChat to coordinate multiple agents
in a research workflow.

Workflow:
1. Planner: Breaks down the query into research steps
2. Researcher: Gathers evidence using web and paper search tools
3. Writer: Synthesizes findings into a coherent response
4. Critic: Evaluates quality and provides feedback
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage

from src.agents.autogen_agents import create_research_team
from src.guardrails.safety_manager import SafetyManager


class AutoGenOrchestrator:
    """
    Orchestrates multi-agent research using AutoGen's RoundRobinGroupChat.
    
    This orchestrator manages a team of specialized agents that work together
    to answer research queries. It uses AutoGen's built-in conversation
    management and tool execution capabilities.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the AutoGen orchestrator.

        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.logger = logging.getLogger("autogen_orchestrator")
        
        # Initialize safety manager
        self.safety_manager = SafetyManager(config)
        
        # Don't create team here - will create fresh for each query
        # to avoid event loop conflicts
        self.team = None
        
        self.logger.info("AutoGen orchestrator initialized")
        
        # Workflow trace for debugging and UI display
        self.workflow_trace: List[Dict[str, Any]] = []

    def process_query(self, query: str, max_rounds: int = 10) -> Dict[str, Any]:
        """
        Process a research query through the multi-agent system.

        Args:
            query: The research question to answer
            max_rounds: Maximum number of conversation rounds

        Returns:
            Dictionary containing:
            - query: Original query
            - response: Final synthesized response
            - conversation_history: Full conversation between agents
            - metadata: Additional information about the process
        """
        self.logger.info(f"Processing query: {query}")
        
        # Check input safety
        safety_check = self.safety_manager.check_input_safety(query)
        if not safety_check.get("safe", True):
            violations = safety_check.get("violations", [])
            violation_msg = "; ".join([v.get("reason", "Unknown") for v in violations])
            self.logger.warning(f"Query blocked by safety guardrails: {violation_msg}")
            return {
                "query": query,
                "error": "Safety violation",
                "response": f"This query violates safety policies: {violation_msg}",
                "conversation_history": [],
                "metadata": {"safety_blocked": True, "reason": violation_msg}
            }
        
        try:
            # Always use asyncio.run() in a new thread to avoid event loop conflicts
            # This ensures AutoGen's internal queues are created in the correct loop
            import nest_asyncio
            import concurrent.futures
            
            def run_async_in_new_loop():
                # Apply nest_asyncio to allow nested loops
                nest_asyncio.apply()
                # Create new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self._process_query_async(query, max_rounds))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(run_async_in_new_loop).result()
            
            # Check output safety
            response_text = result.get("response", "")
            safety_check = self.safety_manager.check_output_safety(response_text)
            if not safety_check.get("safe", True):
                violations = safety_check.get("violations", [])
                violation_msg = "; ".join([v.get("reason", "Unknown") for v in violations])
                sanitized = safety_check.get("sanitized_output", "Response blocked due to safety violations.")
                self.logger.warning(f"Response sanitized by safety guardrails: {violation_msg}")
                result["response"] = sanitized
                result["metadata"]["safety_sanitized"] = True
                result["metadata"]["safety_violations"] = violations
            
            self.logger.info("Query processing complete")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "query": query,
                "error": str(e),
                "response": f"An error occurred while processing your query: {str(e)}",
                "conversation_history": [],
                "metadata": {"error": True}
            }
    
    async def _process_query_async(self, query: str, max_rounds: int = 10) -> Dict[str, Any]:
        """
        Async implementation of query processing.
        
        Args:
            query: The research question to answer
            max_rounds: Maximum number of conversation rounds
            
        Returns:
            Dictionary containing results
        """
        # Create a fresh team for this query to avoid event loop conflicts
        self.logger.info("Creating fresh research team for this query...")
        team = create_research_team(self.config)
        
        # Create task message
        task_message = f"""Research Query: {query}

Please work together to answer this query comprehensively:
1. Planner: Create a research plan
2. Researcher: Gather evidence from web and academic sources
3. Writer: Synthesize findings into a well-cited response
4. Critic: Evaluate the quality and provide feedback"""
        
        # Run the team
        result = await team.run(task=task_message)
        
        # Extract conversation history
        messages = []
        for message in result.messages:
            msg_dict = {
                "source": message.source,
                "content": message.content if hasattr(message, 'content') else str(message),
            }
            messages.append(msg_dict)
        
        # Extract final response - get Writer's substantive research answer
        final_response = ""
        
        # Keywords that indicate closing/farewell messages (not actual content)
        closing_keywords = ["thank you", "best wishes", "take care", "looking forward", 
                           "pleasure", "welcome", "glad", "hope to", "future collaboration"]
        
        if messages:
            # Get Writer's responses, excluding farewell messages
            writer_responses = []
            for msg in reversed(messages):
                if msg.get("source") == "Writer":
                    content = msg.get("content", "").strip()
                    # Check if this is substantive content (not just a closing message)
                    content_lower = content.lower()
                    is_closing = any(keyword in content_lower for keyword in closing_keywords)
                    is_short = len(content) < 200  # Substantive answers are usually longer
                    
                    # Skip if it's a short closing message
                    if not (is_closing and is_short):
                        writer_responses.append(content)
            
            # Use the longest substantive Writer response (likely the main answer)
            if writer_responses:
                final_response = max(writer_responses, key=len)
            
            # If no Writer response found, fall back to any substantive agent message
            if not final_response:
                for msg in reversed(messages):
                    if msg.get("source") not in ["User", "user"]:
                        content = msg.get("content", "").strip()
                        if len(content) > 200:  # Substantive content threshold
                            final_response = content
                            break
        
        # If still no response found, use the last non-user message
        if not final_response and messages:
            for msg in reversed(messages):
                if msg.get("source") not in ["User", "user"]:
                    final_response = msg.get("content", "")
                    if final_response:
                        break
        
        return self._extract_results(query, messages, final_response)

    def _extract_results(self, query: str, messages: List[Dict[str, Any]], final_response: str = "") -> Dict[str, Any]:
        """
        Extract structured results from the conversation history.

        Args:
            query: Original query
            messages: List of conversation messages
            final_response: Final response from the team

        Returns:
            Structured result dictionary
        """
        # Extract components from conversation
        research_findings = []
        plan = ""
        critique = ""
        
        for msg in messages:
            source = msg.get("source", "")
            content = msg.get("content", "")
            
            if source == "Planner" and not plan:
                plan = content
            
            elif source == "Researcher":
                research_findings.append(content)
            
            elif source == "Critic":
                critique = content
        
        # Count sources mentioned in research
        num_sources = 0
        for finding in research_findings:
            # Rough count of sources based on numbered results
            num_sources += finding.count("\n1.") + finding.count("\n2.") + finding.count("\n3.")
        
        # Clean up final response
        if final_response:
            final_response = final_response.replace("TERMINATE", "").strip()
        
        return {
            "query": query,
            "response": final_response,
            "conversation_history": messages,
            "metadata": {
                "num_messages": len(messages),
                "num_sources": max(num_sources, 1),  # At least 1
                "plan": plan,
                "research_findings": research_findings,
                "critique": critique,
                "agents_involved": list(set([msg.get("source", "") for msg in messages])),
            }
        }

    def get_agent_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions of all agents.

        Returns:
            Dictionary mapping agent names to their descriptions
        """
        return {
            "Planner": "Breaks down research queries into actionable steps",
            "Researcher": "Gathers evidence from web and academic sources",
            "Writer": "Synthesizes findings into coherent responses",
            "Critic": "Evaluates quality and provides feedback",
        }

    def visualize_workflow(self) -> str:
        """
        Generate a text visualization of the workflow.

        Returns:
            String representation of the workflow
        """
        workflow = """
AutoGen Research Workflow:

1. User Query
   ↓
2. Planner
   - Analyzes query
   - Creates research plan
   - Identifies key topics
   ↓
3. Researcher (with tools)
   - Uses web_search() tool
   - Uses paper_search() tool
   - Gathers evidence
   - Collects citations
   ↓
4. Writer
   - Synthesizes findings
   - Creates structured response
   - Adds citations
   ↓
5. Critic
   - Evaluates quality
   - Checks completeness
   - Provides feedback
   ↓
6. Decision Point
   - If APPROVED → Final Response
   - If NEEDS REVISION → Back to Writer
        """
        return workflow


def demonstrate_usage():
    """
    Demonstrate how to use the AutoGen orchestrator.
    
    This function shows a simple example of using the orchestrator.
    """
    import yaml
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Create orchestrator
    orchestrator = AutoGenOrchestrator(config)
    
    # Print workflow visualization
    print(orchestrator.visualize_workflow())
    
    # Example query
    query = "What are the latest trends in human-computer interaction research?"
    
    print(f"\nProcessing query: {query}\n")
    print("=" * 70)
    
    # Process query
    result = orchestrator.process_query(query)
    
    # Display results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\nQuery: {result['query']}")
    print(f"\nResponse:\n{result['response']}")
    print(f"\nMetadata:")
    print(f"  - Messages exchanged: {result['metadata']['num_messages']}")
    print(f"  - Sources gathered: {result['metadata']['num_sources']}")
    print(f"  - Agents involved: {', '.join(result['metadata']['agents_involved'])}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    demonstrate_usage()

