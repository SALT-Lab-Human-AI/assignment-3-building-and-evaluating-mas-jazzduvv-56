"""
Command Line Interface
Interactive CLI for the multi-agent research system.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from typing import Dict, Any
import yaml
import json
import logging
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

from src.autogen_orchestrator import AutoGenOrchestrator
from src.tools.citation_tool import CitationTool

# Load environment variables
load_dotenv()

# Ensure outputs directory exists
Path("outputs").mkdir(exist_ok=True)

class CLI:
    """
    Command-line interface for the research assistant.

    TODO: YOUR CODE HERE
    - Implement interactive prompt loop
    - Display agent traces clearly
    - Show citations and sources
    - Indicate safety events (blocked/sanitized)
    - Handle user commands (help, quit, clear, etc.)
    - Format output nicely
    """

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize CLI.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        self._setup_logging()

        # Initialize AutoGen orchestrator
        try:
            self.orchestrator = AutoGenOrchestrator(self.config)
            self.logger = logging.getLogger("cli")
            self.logger.info("AutoGen orchestrator initialized successfully")
        except Exception as e:
            self.logger = logging.getLogger("cli")
            self.logger.error(f"Failed to initialize orchestrator: {e}")
            raise

        self.running = True
        self.query_count = 0

    def _setup_logging(self):
        """Setup logging configuration."""
        log_config = self.config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_format = log_config.get(
            "format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format
        )

    async def run(self):
        """
        Main CLI loop.

        TODO: YOUR CODE HERE
        - Implement interactive loop
        - Handle user input
        - Process queries through orchestrator
        - Display results
        - Handle errors gracefully
        """
        self._print_welcome()

        while self.running:
            try:
                # Get user input
                query = input("\nEnter your research query (or 'help' for commands): ").strip()

                if not query:
                    continue

                # Handle commands
                if query.lower() in ['quit', 'exit', 'q']:
                    self._print_goodbye()
                    break
                elif query.lower() == 'help':
                    self._print_help()
                    continue
                elif query.lower() == 'clear':
                    self._clear_screen()
                    continue
                elif query.lower() == 'stats':
                    self._print_stats()
                    continue

                # Process query
                print("\n" + "=" * 70)
                print("Processing your query...")
                print("=" * 70)
                
                try:
                    # Process through orchestrator (synchronous call, not async)
                    result = self.orchestrator.process_query(query)
                    self.query_count += 1
                    
                    # Save session to JSON file
                    try:
                        session_file = self._save_session_json(query, result)
                        print(f"\n✅ Session saved to: {session_file}")
                    except Exception as e:
                        print(f"\n⚠️  Could not save session file: {e}")
                    
                    # Display result
                    self._display_result(result)
                    
                except Exception as e:
                    print(f"\nError processing query: {e}")
                    logging.exception("Error processing query")

            except KeyboardInterrupt:
                print("\n\nInterrupted by user.")
                self._print_goodbye()
                break
            except Exception as e:
                print(f"\nError: {e}")
                logging.exception("Error in CLI loop")

    def _print_welcome(self):
        """Print welcome message."""
        print("=" * 70)
        print(f"  {self.config['system']['name']}")
        print(f"  Topic: {self.config['system']['topic']}")
        print("=" * 70)
        print("\nWelcome! Ask me anything about your research topic.")
        print("Type 'help' for available commands, or 'quit' to exit.\n")

    def _print_help(self):
        """Print help message."""
        print("\nAvailable commands:")
        print("  help    - Show this help message")
        print("  clear   - Clear the screen")
        print("  stats   - Show system statistics")
        print("  quit    - Exit the application")
        print("\nOr enter a research query to get started!")

    def _print_goodbye(self):
        """Print goodbye message."""
        print("\nThank you for using the Multi-Agent Research Assistant!")
        print("Goodbye!\n")

    def _clear_screen(self):
        """Clear the terminal screen."""
        import os
        os.system('clear' if os.name == 'posix' else 'cls')

    def _print_stats(self):
        """Print system statistics."""
        print("\nSystem Statistics:")
        print(f"  Queries processed: {self.query_count}")
        print(f"  System: {self.config.get('system', {}).get('name', 'Unknown')}")
        print(f"  Topic: {self.config.get('system', {}).get('topic', 'Unknown')}")
        print(f"  Model: {self.config.get('models', {}).get('default', {}).get('name', 'Unknown')}")

    def _display_result(self, result: Dict[str, Any]):
        """Display query result with formatting."""
        print("\n" + "=" * 70)
        print("RESPONSE")
        print("=" * 70)

        # Check for errors
        if "error" in result:
            print(f"\n❌ Error: {result['error']}")
            return

        # Display response
        response = result.get("response", "")
        # Handle response being a list or other non-string type
        if isinstance(response, list):
            response = " ".join(str(item) for item in response)
        elif not isinstance(response, str):
            response = str(response)
        print(f"\n{response}\n")

        # Extract and display citations from conversation in APA format
        citations = self._extract_citations(result)
        if citations:
            print("\n" + "-" * 70)
            print("📚 CITATIONS (APA Format)")
            print("-" * 70)
            for i, citation_data in enumerate(citations, 1):
                if isinstance(citation_data, dict):
                    print(f"[{i}] {citation_data.get('formatted', citation_data.get('url', ''))}")
                else:
                    print(f"[{i}] {citation_data}")

        # Display metadata
        metadata = result.get("metadata", {})
        if metadata:
            print("\n" + "-" * 70)
            print("📊 METADATA")
            print("-" * 70)
            print(f"  • Messages exchanged: {metadata.get('num_messages', 0)}")
            print(f"  • Sources gathered: {metadata.get('num_sources', 0)}")
            print(f"  • Agents involved: {', '.join(metadata.get('agents_involved', []))}")

        # Display conversation summary if verbose mode
        if self._should_show_traces():
            self._display_conversation_summary(result.get("conversation_history", []))

        print("=" * 70 + "\n")
    
    def _save_session_json(self, query: str, result: Dict[str, Any]) -> str:
        """Save session data to JSON file in outputs folder."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        def make_serializable(obj):
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            if isinstance(obj, (list, tuple)):
                return [make_serializable(i) for i in obj]
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            return str(obj)
        
        formatted_history = []
        for i, msg in enumerate(result.get("metadata", {}).get("conversation_history", [])):
            if isinstance(msg, dict):
                source = msg.get('source', 'unknown')
                content = msg.get('content', '')
            else:
                source = getattr(msg, 'source', getattr(msg, 'role', 'unknown'))
                content = getattr(msg, 'content', str(msg))
            
            formatted_history.append({
                "index": i,
                "role": "assistant" if source in ["Planner", "Researcher", "Writer", "Critic"] else "user",
                "name": source,
                "content": str(content) if not isinstance(content, str) else content
            })
        
        session_data = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "conversation_history": formatted_history,
            "response": result.get("response", ""),
            "metadata": make_serializable(result.get("metadata", {})),
            "citations": self._extract_citations(result)
        }
        
        session_file = f"outputs/cli_session_{timestamp}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        return session_file
    
    def _extract_citations(self, result: Dict[str, Any]) -> list:
        """Extract citations/URLs from conversation history and format in APA style."""
        import re
        citations = []
        seen_urls = set()
        
        for msg in result.get("conversation_history", []):
            content = msg.get("content", "")
            
            # Handle content being a list or other non-string type
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            elif not isinstance(content, str):
                content = str(content)
            
            # Find URLs in content
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
            
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

    def _should_show_traces(self) -> bool:
        """Check if agent traces should be displayed."""
        # Check config for verbose mode
        return self.config.get("ui", {}).get("verbose", False)

    def _display_conversation_summary(self, conversation_history: list):
        """Display a summary of the agent conversation."""
        if not conversation_history:
            return
            
        print("\n" + "-" * 70)
        print("🔍 CONVERSATION SUMMARY")
        print("-" * 70)
        
        for i, msg in enumerate(conversation_history, 1):
            agent = msg.get("source", "Unknown")
            content = msg.get("content", "")
            
            # Handle content being a list or other non-string type
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            elif not isinstance(content, str):
                content = str(content)
            
            # Truncate long content
            preview = content[:150] + "..." if len(content) > 150 else content
            preview = preview.replace("\n", " ")
            
            print(f"\n{i}. {agent}:")
            print(f"   {preview}")


def main():
    """Main entry point for CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-Agent Research Assistant CLI"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file"
    )

    args = parser.parse_args()

    # Run CLI
    cli = CLI(config_path=args.config)
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
