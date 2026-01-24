#!/usr/bin/env python3
"""
Gradescope to Google Calendar Sync Script

This script syncs assignments from Gradescope to Google Calendar.
It handles duplicate prevention and updates existing events when due dates change.

Environment Variables Required:
- GRADESCOPE_EMAIL: Your Gradescope email address
- GRADESCOPE_PASSWORD: Your Gradescope password
- GOOGLE_TOKEN: Base64-encoded contents of token.json (for GitHub Actions)

For local development, place credentials.json and token.json in the same directory.
"""

import os
import sys
import json
import base64
from pathlib import Path

def setup_google_credentials():
    """Set up Google credentials from environment variable or local file."""
    token_path = Path(__file__).parent / "token.json"

    # Check if running in GitHub Actions (token passed as env var)
    google_token = os.environ.get("GOOGLE_TOKEN")
    if google_token:
        try:
            # Decode base64 token and write to file
            token_data = base64.b64decode(google_token).decode("utf-8")
            token_path.write_text(token_data)
            print("Google credentials loaded from environment variable.")
        except Exception as e:
            print(f"Error decoding GOOGLE_TOKEN: {e}")
            sys.exit(1)
    elif token_path.exists():
        print("Using local token.json file.")
    else:
        print("ERROR: No Google credentials found.")
        print("Either set GOOGLE_TOKEN environment variable or run setup_google_auth.py first.")
        sys.exit(1)

def main():
    """Main sync function."""
    # Get Gradescope credentials from environment
    email = os.environ.get("GRADESCOPE_EMAIL")
    password = os.environ.get("GRADESCOPE_PASSWORD")

    if not email or not password:
        print("ERROR: Missing Gradescope credentials.")
        print("Set GRADESCOPE_EMAIL and GRADESCOPE_PASSWORD environment variables.")
        sys.exit(1)

    # Set up Google credentials
    setup_google_credentials()

    try:
        from gradescopecalendar.gradescopecalendar import GradescopeCalendar

        print(f"Logging into Gradescope as {email}...")
        calendar = GradescopeCalendar(email, password, is_instructor=False)

        print("Syncing assignments to Google Calendar...")
        calendar.write_to_gcal()

        print("Sync completed successfully!")

    except ImportError:
        print("ERROR: gradescopecalendar package not installed.")
        print("Run: pip install gradescopecalendar")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Sync failed - {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
