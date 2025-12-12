"""
Main Entry Point
Can be used to run the system or evaluation.

Usage:
  python main.py --mode cli           # Run CLI interface
  python main.py --mode web           # Run web interface
  python main.py --mode evaluate      # Run evaluation
"""

import argparse
import asyncio
import sys
from pathlib import Path


def run_cli():
    """Run CLI interface."""
    # Remove main.py's --mode argument before calling CLI
    import sys
    filtered_args = []
    skip_next = False
    for i, arg in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if arg == '--mode':
            skip_next = True  # Skip the next argument (the mode value)
            continue
        filtered_args.append(arg)
    sys.argv = [sys.argv[0]] + filtered_args
    
    from src.ui.cli import main as cli_main
    cli_main()


def run_web():
    """Run web interface."""
    import subprocess
    print("Starting Streamlit web interface...")
    subprocess.run(["streamlit", "run", "src/ui/streamlit_app.py"])


async def run_evaluation():
    """Run system evaluation with LLM-as-a-Judge."""
    import yaml
    from dotenv import load_dotenv
    from src.autogen_orchestrator import AutoGenOrchestrator
    from src.evaluation.evaluator import SystemEvaluator
    
    # Load environment variables
    load_dotenv()

    # Load config
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)

    # Initialize AutoGen orchestrator
    print("Initializing AutoGen orchestrator...")
    orchestrator = AutoGenOrchestrator(config)
    
    # Initialize SystemEvaluator
    print("Initializing SystemEvaluator with LLM-as-a-Judge...")
    evaluator = SystemEvaluator(config, orchestrator=orchestrator)
    
    # Run full evaluation
    print("\n" + "=" * 70)
    print("RUNNING FULL SYSTEM EVALUATION")
    print("=" * 70)
    
    results = await evaluator.evaluate_system("data/example_queries.json")
    
    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print(f"\nTotal Queries: {results.get('total_queries', 0)}")
    print(f"Overall Average Score: {results.get('overall_average', 0):.2f}")
    print(f"\nResults saved to: {results.get('output_file', 'outputs/')}")
    
    # Print summary statistics
    if 'criterion_averages' in results:
        print("\n" + "=" * 70)
        print("CRITERION AVERAGES")
        print("=" * 70)
        for criterion, score in results['criterion_averages'].items():
            print(f"  {criterion}: {score:.2f}")
    
    print("\n" + "=" * 70)


def run_autogen():
    """Run AutoGen example."""
    import subprocess
    print("Running AutoGen example...")
    subprocess.run([sys.executable, "example_autogen.py"])


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Research Assistant"
    )
    parser.add_argument(
        "--mode",
        choices=["cli", "web", "evaluate", "autogen"],
        default="autogen",
        help="Mode to run: cli, web, evaluate, or autogen (default)"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file"
    )

    args = parser.parse_args()

    if args.mode == "cli":
        run_cli()
    elif args.mode == "web":
        run_web()
    elif args.mode == "evaluate":
        asyncio.run(run_evaluation())
    elif args.mode == "autogen":
        run_autogen()


if __name__ == "__main__":
    main()
