"""
Demo Script - End-to-End Multi-Agent Research System
Runs a complete example: Query → Agents → Synthesis → Judge Scoring

Usage:
    python demo.py
    
This script demonstrates:
1. Query input and safety validation
2. Multi-agent conversation (Planner → Researcher → Writer → Critic)
3. Final response synthesis with citations
4. LLM-as-a-Judge evaluation with 5 criteria
"""

import asyncio
import sys
import os
import yaml
import json
from datetime import datetime
from dotenv import load_dotenv

# Set UTF-8 encoding for console output on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.autogen_orchestrator import AutoGenOrchestrator
from src.evaluation.judge import LLMJudge


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


def print_agent_message(agent, message, step=None):
    """Print an agent message with formatting."""
    agent_emoji = {
        "Planner": "📋",
        "Researcher": "🔍", 
        "Writer": "✍️",
        "Critic": "⚖️"
    }
    emoji = agent_emoji.get(agent, "💬")
    
    if step:
        print(f"\n{emoji} Step {step}: {agent}")
    else:
        print(f"\n{emoji} {agent}:")
    
    print("-" * 80)
    # Show more content (increased from 500 to 2000 characters)
    if len(message) > 2000:
        print(message[:2000] + f"\n... (truncated for display, see output files for full content)")
    else:
        print(message)


async def run_demo():
    """Run the complete end-to-end demo."""
    
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    print_header("MULTI-AGENT RESEARCH SYSTEM - END-TO-END DEMO")
    print("This demo will:")
    print("  1. Process a research query through 4 specialized agents")
    print("  2. Show agent-to-agent communication")
    print("  3. Synthesize a final response with citations")
    print("  4. Evaluate the response using LLM-as-a-Judge")
    
    # Demo query
    query = "How can procedural generation techniques be combined with machine learning for world building?"
    
    print_header("STEP 1: QUERY INPUT")
    print(f"Query: {query}")
    print(f"\nQuery Category: Hybrid Generation (Procedural + ML)")
    print(f"Expected Topics: PCG techniques, GANs, NeRF, controllable generation")
    
    # Initialize orchestrator
    print_header("STEP 2: INITIALIZING MULTI-AGENT SYSTEM")
    print("Creating 4 specialized agents:")
    print("  📋 Planner   - Breaks down query into research steps")
    print("  🔍 Researcher - Gathers evidence from web and academic sources")
    print("  ✍️ Writer    - Synthesizes findings into coherent response")
    print("  ⚖️ Critic    - Evaluates quality and provides feedback")
    
    orchestrator = AutoGenOrchestrator(config)
    
    # Process query
    print_header("STEP 3: MULTI-AGENT PROCESSING")
    print("Starting agent conversation...")
    print("(This may take 30-60 seconds)")
    
    result = orchestrator.process_query(query)
    
    # Check for errors
    if "error" in result:
        print(f"\n❌ Error: {result['error']}")
        print(f"Details: {result.get('response', 'Unknown error')}")
        return
    
    # Display agent conversation
    print_header("STEP 4: AGENT CONVERSATION TRACES")
    
    conversation_history = result.get("conversation_history", [])
    if conversation_history:
        step = 1
        for msg in conversation_history:
            agent = msg.get("source", "Unknown")
            content = msg.get("content", "")
            
            # Skip system messages and empty content
            if agent in ["Planner", "Researcher", "Writer", "Critic"] and content:
                print_agent_message(agent, content, step)
                step += 1
    else:
        print("No conversation history available.")
    
    # Display final response
    print_header("STEP 5: FINAL SYNTHESIZED RESPONSE")
    
    response_text = result.get("response", "No response generated")
    print(response_text)
    
    # Display metadata
    print_header("STEP 6: RESPONSE METADATA")
    
    metadata = result.get("metadata", {})
    
    if "sources" in metadata:
        sources = metadata["sources"]
        print(f"📚 Sources Used: {len(sources)}")
        for i, source in enumerate(sources[:5], 1):  # Show first 5
            print(f"  {i}. {source.get('title', 'Unknown')} - {source.get('url', 'N/A')}")
    
    if "safety_events" in metadata:
        safety_events = metadata["safety_events"]
        if safety_events:
            print(f"\n⚠️ Safety Events: {len(safety_events)}")
            for event in safety_events:
                print(f"  - {event.get('type', 'Unknown')}: {event.get('message', 'N/A')}")
        else:
            print("\n✅ No safety violations detected")
    
    # Evaluate with judge
    print_header("STEP 7: LLM-AS-A-JUDGE EVALUATION")
    print("Evaluating response across 5 criteria...")
    
    judge = LLMJudge(config)
    
    sources = metadata.get("sources", [])
    evaluation = await judge.evaluate(
        query=query,
        response=response_text,
        sources=sources,
        ground_truth=None
    )
    
    # Display evaluation results
    print_header("STEP 8: EVALUATION RESULTS")
    
    overall_score = evaluation.get("overall_score", 0.0)
    print(f"\n🎯 Overall Score: {overall_score:.3f} / 1.0 ({overall_score*100:.1f}%)\n")
    
    criterion_scores = evaluation.get("criterion_scores", {})
    
    print("Criterion Breakdown:")
    print("-" * 80)
    
    criteria_config = config.get("evaluation", {}).get("criteria", [])
    for criterion_config in criteria_config:
        criterion_name = criterion_config.get("name")
        weight = criterion_config.get("weight", 0.0)
        
        if criterion_name in criterion_scores:
            score_data = criterion_scores[criterion_name]
            score = score_data.get("score", 0.0)
            reasoning = score_data.get("reasoning", "No reasoning provided")
            
            print(f"\n📊 {criterion_name.upper()}")
            print(f"   Score: {score:.2f} / 1.0 (Weight: {weight*100:.0f}%)")
            print(f"   Reasoning: {reasoning[:200]}...")
    
    # Save demo results
    print_header("STEP 9: SAVING DEMO RESULTS")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create outputs directory if it doesn't exist
    Path("outputs").mkdir(exist_ok=True)
    
    # Helper function to make objects JSON serializable
    def make_serializable(obj):
        """Recursively convert objects to JSON-serializable types while preserving structure."""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # For objects with __dict__, preserve their attributes as a dict
            obj_dict = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    obj_dict[key] = make_serializable(value)
            return {
                '_type': obj.__class__.__name__,
                **obj_dict
            }
        else:
            # Last resort: convert to string representation
            return str(obj)
    
    # Convert conversation history to better format
    formatted_history = []
    for i, msg in enumerate(conversation_history):
        # Handle both dict and object types
        if isinstance(msg, dict):
            # Already a dictionary
            source = msg.get('source', 'unknown')
            content = msg.get('content', '')
            formatted_msg = {
                "index": i,
                "role": "assistant" if source in ["Planner", "Researcher", "Writer", "Critic"] else "user",
                "name": source,
                "content": str(content) if not isinstance(content, str) else content
            }
        else:
            # Object with attributes
            source = getattr(msg, 'source', getattr(msg, 'role', 'unknown'))
            content = getattr(msg, 'content', msg)
            formatted_msg = {
                "index": i,
                "role": getattr(msg, 'role', 'assistant' if source in ["Planner", "Researcher", "Writer", "Critic"] else "user"),
                "name": source,
                "content": str(content) if not isinstance(content, str) else content
            }
            
            # Add tool calls if present
            if hasattr(msg, 'content') and hasattr(msg.content, 'tool_calls'):
                formatted_msg["tool_calls"] = make_serializable(msg.content.tool_calls)
        
        formatted_history.append(formatted_msg)
        formatted_history.append(formatted_msg)
    
    serializable_history = formatted_history
    
    # Save full session
    session_file = f"outputs/demo_session_{timestamp}.json"
    with open(session_file, 'w') as f:
        json.dump({
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "conversation_history": serializable_history,
            "response": response_text,
            "metadata": make_serializable(metadata),
            "evaluation": make_serializable(evaluation)
        }, f, indent=2)
    
    print(f"✅ Full session saved to: {session_file}")
    
    # Save response only
    response_file = f"outputs/demo_response_{timestamp}.md"
    with open(response_file, 'w') as f:
        f.write(f"# Demo Response\n\n")
        f.write(f"**Query**: {query}\n\n")
        f.write(f"**Timestamp**: {datetime.now().isoformat()}\n\n")
        f.write(f"---\n\n")
        f.write(response_text)
        f.write(f"\n\n---\n\n")
        f.write(f"**Overall Score**: {overall_score:.3f} / 1.0\n")
    
    print(f"✅ Response saved to: {response_file}")
    
    # Save judge outputs
    judge_file = f"outputs/demo_judge_{timestamp}.json"
    with open(judge_file, 'w') as f:
        json.dump(evaluation, f, indent=2)
    
    print(f"✅ Judge evaluation saved to: {judge_file}")
    
    # Final summary
    print_header("DEMO COMPLETE!")
    
    print("Summary:")
    print(f"  • Query processed successfully through 4 agents")
    print(f"  • Response generated with {len(sources)} sources" if sources else "  • Response generated")
    print(f"  • Overall evaluation score: {overall_score:.3f} / 1.0")
    print(f"  • All outputs saved to outputs/ directory")
    
    print("\nNext Steps:")
    print("  • Review the saved files in outputs/")
    print("  • Run the Streamlit UI: python -m streamlit run src/ui/streamlit_app.py")
    print("  • Run full evaluation: python main.py --mode evaluate")
    
    print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point."""
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error running demo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
