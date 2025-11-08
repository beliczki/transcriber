#!/usr/bin/env python3
"""
Transcriber Service - Entry Point
Dual-engine STT with LLM consolidation
"""

import os
import sys
from app.config import Config
from app.models import init_db

def create_directories():
    """Create necessary directories if they don't exist."""
    directories = ['data', 'logs']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")


def main():
    """Main entry point for the Transcriber service."""
    print("=" * 60)
    print("Transcriber Service - Phase 1 MVP")
    print("Dual-Engine STT with LLM Consolidation")
    print("=" * 60)

    # Create necessary directories
    create_directories()

    # Load and validate configuration
    try:
        print("\nValidating configuration...")
        Config.validate()
        print("[OK] Configuration valid")
    except ValueError as e:
        print("\n[ERROR] Configuration Error:")
        print(str(e))
        print("\nPlease update your .env file with the required settings.")
        sys.exit(1)

    # Initialize database
    try:
        print("\nInitializing database...")
        init_db(Config.DATABASE_URL)
        print("[OK] Database initialized")
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed:")
        print(str(e))
        sys.exit(1)

    # TODO: Initialize Flask-SocketIO server
    print("\n" + "=" * 60)
    print("Server initialization complete!")
    print("=" * 60)
    print("\nNOTE: Flask-SocketIO server not yet implemented.")
    print("This is the foundation test - database and config are working!")
    print("\nNext steps:")
    print("  1. Implement services (STT, session management)")
    print("  2. Implement WebSocket handlers")
    print("  3. Start Flask-SocketIO server")
    print("=" * 60)


if __name__ == '__main__':
    main()
