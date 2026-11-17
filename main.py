"""
Main entrypoint alias for backwards compatibility.
Runs CLI from src.cli.main.
"""

from run import run_cli

if __name__ == "__main__":
    run_cli()
