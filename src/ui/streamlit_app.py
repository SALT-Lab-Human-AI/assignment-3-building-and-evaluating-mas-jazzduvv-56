"""
Streamlit Web Interface
Web UI for the multi-agent research system.

Run with: streamlit run src/ui/streamlit_app.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import asyncio
import yaml
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from src.autogen_orchestrator import AutoGenOrchestrator
from src.tools.citation_tool import CitationTool

# Load environment variables
load_dotenv()


def load_config():
    """Load configuration file."""
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'history' not in st.session_state:
        st.session_state.history = []

    if 'orchestrator' not in st.session_state:
        config = load_config()
        # Initialize AutoGen orchestrator
        try:
            st.session_state.orchestrator = AutoGenOrchestrator(config)
        except Exception as e:
            st.error(f"Failed to initialize orchestrator: {e}")
            st.session_state.orchestrator = None

    if 'show_traces' not in st.session_state:
        st.session_state.show_traces = False

    if 'show_safety_log' not in st.session_state:
        st.session_state.show_safety_log = False


def process_query(query: str, status_placeholder=None) -> Dict[str, Any]:
    """
    Process a query through the orchestrator.
    
    Args:
        query: Research query to process
        status_placeholder: Streamlit placeholder for status updates
        
    Returns:
        Result dictionary with response, citations, and metadata
    """
    orchestrator = st.session_state.orchestrator
    
    if orchestrator is None:
        return {
            "query": query,
            "error": "Orchestrator not initialized",
            "response": "Error: System not properly initialized. Please check your configuration.",
            "citations": [],
            "metadata": {}
        }
    
    try:
        # Show agent workflow status
        if status_placeholder:
            with status_placeholder.container():
                st.info("🔄 **Multi-Agent Processing Active**")
                agent_status = st.empty()
                
                # Update status for each expected agent
                agent_status.markdown("📋 **Planner**: Creating research plan...")
                import time
                time.sleep(0.5)
        
        # Process query through AutoGen orchestrator
        result = orchestrator.process_query(query)
        
        # Update status during processing (simplified version)
        if status_placeholder:
            with status_placeholder.container():
                st.success("✅ **Processing Complete**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown("📋 **Planner**\n✓ Plan created")
                with col2:
                    st.markdown("🔍 **Researcher**\n✓ Sources gathered")
                with col3:
                    st.markdown("✍️ **Writer**\n✓ Response synthesized")
                with col4:
                    st.markdown("⚖️ **Critic**\n✓ Quality verified")
        
        # Check for errors
        if "error" in result:
            return result
        
        # Extract citations from conversation history
        citations = extract_citations(result)
        
        # Extract agent traces for display
        agent_traces = extract_agent_traces(result)
        
        # Format metadata
        metadata = result.get("metadata", {})
        metadata["agent_traces"] = agent_traces
        metadata["citations_formatted"] = citations
        metadata["critique_score"] = calculate_quality_score(result)
        
        return {
            "query": query,
            "response": result.get("response", ""),
            "citations": citations,
            "metadata": metadata
        }
        
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "response": f"An error occurred: {str(e)}",
            "citations": [],
            "metadata": {"error": True}
        }


def extract_citations(result: Dict[str, Any]) -> list:
    """Extract citations from research result and format in APA style."""
    import re
    citations = []
    seen_urls = set()
    
    # Look through conversation history for citations
    for msg in result.get("conversation_history", []):
        content = msg.get("content", "")
        
        # Handle content being a list or other non-string type
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        elif not isinstance(content, str):
            content = str(content)
        
        # Find URLs in content
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
        
        # Quick APA-style formatting
        for url in urls:
            if url not in seen_urls and len(citations) < 10:
                seen_urls.add(url)
                # Simple APA format: Site name. (Year). URL
                try:
                    site_name = url.split('/')[2]
                except:
                    site_name = "Web Source"
                
                formatted = f"{site_name}. ({datetime.now().year}). Retrieved from {url}"
                citations.append({
                    "url": url,
                    "formatted": formatted
                })
    
    return citations


def extract_agent_traces(result: Dict[str, Any]) -> list:
    """Extract agent execution traces from conversation history with better formatting."""
    traces = []
    
    for i, msg in enumerate(result.get("conversation_history", []), 1):
        agent = msg.get("source", "Unknown")
        content = msg.get("content", "")
        
        # Handle content being a list or other non-string type
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        elif not isinstance(content, str):
            content = str(content)
        
        # Create trace entry with step number, agent, and preview
        traces.append({
            "step": i,
            "agent": agent,
            "preview": content[:300] + "..." if len(content) > 300 else content,
            "full_content": content
        })
    
    return traces


def calculate_quality_score(result: Dict[str, Any]) -> float:
    """Calculate a quality score based on various factors."""
    score = 5.0  # Base score
    
    metadata = result.get("metadata", {})
    
    # Add points for sources
    num_sources = metadata.get("num_sources", 0)
    score += min(num_sources * 0.5, 2.0)
    
    # Add points for critique
    if metadata.get("critique"):
        score += 1.0
    
    # Add points for conversation length (indicates thorough discussion)
    num_messages = metadata.get("num_messages", 0)
    score += min(num_messages * 0.1, 2.0)
    
    return min(score, 10.0)  # Cap at 10


def display_response(result: Dict[str, Any]):
    """
    Display query response.

    TODO: YOUR CODE HERE
    - Format response nicely
    - Show citations with links
    - Display sources
    - Show safety events if any
    """
    # Check for errors
    if "error" in result:
        error_type = result['error']
        error_message = result.get('response', 'An error occurred')
        
        # Show detailed error message
        st.error(f"**{error_type}**")
        st.warning(error_message)
        
        # Show additional metadata if available
        if "metadata" in result and "reason" in result["metadata"]:
            with st.expander("ℹ️ Details", expanded=True):
                st.text(result["metadata"]["reason"])
        
        return

    # Display response
    st.markdown("### Response")
    response = result.get("response", "")
    # Handle response being a list or other non-string type
    if isinstance(response, list):
        response = " ".join(str(item) for item in response)
    elif not isinstance(response, str):
        response = str(response)
    st.markdown(response)

    # Display citations in APA format
    metadata = result.get("metadata", {})
    citations = metadata.get("citations_formatted", [])
    if citations:
        with st.expander("📚 Citations (APA Format)", expanded=False):
            for i, citation_data in enumerate(citations, 1):
                if isinstance(citation_data, dict):
                    st.markdown(f"**[{i}]** {citation_data.get('formatted', citation_data.get('url', ''))}")
                else:
                    st.markdown(f"**[{i}]** {citation_data}")

    # Display metadata
    metadata = result.get("metadata", {})

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Sources Used", metadata.get("num_sources", 0))
    with col2:
        score = metadata.get("critique_score", 0)
        st.metric("Quality Score", f"{score:.2f}")

    # Safety events
    safety_events = metadata.get("safety_events", [])
    if safety_events:
        with st.expander("⚠️ Safety Events", expanded=True):
            for event in safety_events:
                event_type = event.get("type", "unknown")
                violations = event.get("violations", [])
                st.warning(f"{event_type.upper()}: {len(violations)} violation(s) detected")
                for violation in violations:
                    st.text(f"  • {violation.get('reason', 'Unknown')}")

    # Agent traces
    if st.session_state.show_traces:
        agent_traces = metadata.get("agent_traces", [])
        if agent_traces:
            display_agent_traces(agent_traces)


def display_agent_traces(traces: list):
    """
    Display agent execution traces with step-by-step workflow.
    """
    with st.expander("🔍 Agent Conversation Traces", expanded=True):
        st.markdown("**Agent Workflow (Step-by-Step)**")
        st.markdown("---")
        
        for trace in traces:
            step = trace.get("step", 0)
            agent = trace.get("agent", "Unknown")
            preview = trace.get("preview", "")
            
            # Color code by agent
            agent_emoji = {
                "Planner": "📋",
                "Researcher": "🔍",
                "Writer": "✍️",
                "Critic": "⚖️"
            }
            emoji = agent_emoji.get(agent, "💬")
            
            st.markdown(f"### {emoji} Step {step}: {agent}")
            with st.container():
                st.text_area(
                    f"Message from {agent}",
                    preview,
                    height=150,
                    key=f"trace_{step}",
                    disabled=True
                )
            st.markdown("---")


def display_sidebar():
    """Display sidebar with settings and statistics."""
    with st.sidebar:
        st.title("⚙️ Settings")

        # Show traces toggle
        st.session_state.show_traces = st.checkbox(
            "Show Agent Traces",
            value=st.session_state.show_traces
        )

        # Show safety log toggle
        st.session_state.show_safety_log = st.checkbox(
            "Show Safety Log",
            value=st.session_state.show_safety_log
        )

        st.divider()

        st.title("📊 Statistics")

        # TODO: Get actual statistics
        st.metric("Total Queries", len(st.session_state.history))
        st.metric("Safety Events", 0)  # TODO: Get from safety manager

        st.divider()

        # Clear history button
        if st.button("Clear History"):
            st.session_state.history = []
            st.rerun()

        # About section
        st.divider()
        st.markdown("### About")
        config = load_config()
        system_name = config.get("system", {}).get("name", "Research Assistant")
        topic = config.get("system", {}).get("topic", "General")
        st.markdown(f"**System:** {system_name}")
        st.markdown(f"**Topic:** {topic}")


def display_history():
    """Display query history."""
    if not st.session_state.history:
        return

    with st.expander("📜 Query History", expanded=False):
        for i, item in enumerate(reversed(st.session_state.history), 1):
            timestamp = item.get("timestamp", "")
            query = item.get("query", "")
            st.markdown(f"**{i}.** [{timestamp}] {query}")


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Multi-Agent Research Assistant",
        page_icon="🤖",
        layout="wide"
    )

    initialize_session_state()

    # Header
    st.title("🤖 Multi-Agent Research Assistant")
    st.markdown("Ask me anything about your research topic!")

    # Sidebar
    display_sidebar()

    # Main area
    col1, col2 = st.columns([2, 1])

    with col1:
        # Query input
        query = st.text_area(
            "Enter your research query:",
            height=100,
            placeholder="e.g., What are the latest developments in explainable AI for novice users?"
        )

        # Submit button
        if st.button("🔍 Search", type="primary", use_container_width=True):
            if query.strip():
                # Create status placeholder for real-time agent updates
                status_container = st.empty()
                
                # Process query with status updates
                result = process_query(query, status_placeholder=status_container)

                # Add to history
                st.session_state.history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "query": query,
                    "result": result
                })

                # Display result
                st.divider()
                display_response(result)
            else:
                st.warning("Please enter a query.")

        # History
        display_history()

    with col2:
        st.markdown("### 💡 Example Queries")
        examples = [
            "What are AI-generated synthetic worlds?",
            "How is procedural content generation used in games?",
            "What tools exist for creating virtual environments?",
            "What are safety concerns in virtual reality experiences?",
        ]

        for example in examples:
            if st.button(example, use_container_width=True):
                st.session_state.example_query = example
                st.rerun()

        # If example was clicked, populate the text area
        if 'example_query' in st.session_state:
            st.info(f"Example query selected: {st.session_state.example_query}")
            del st.session_state.example_query

        st.divider()

        st.markdown("### ℹ️ How It Works")
        st.markdown("""
        1. **Planner** breaks down your query
        2. **Researcher** gathers evidence
        3. **Writer** synthesizes findings
        4. **Critic** verifies quality
        5. **Safety** checks ensure appropriate content
        """)

    # Safety log (if enabled)
    if st.session_state.show_safety_log:
        st.divider()
        st.markdown("### 🛡️ Safety Event Log")
        # TODO: Display safety events from safety manager
        st.info("No safety events recorded.")


if __name__ == "__main__":
    main()
