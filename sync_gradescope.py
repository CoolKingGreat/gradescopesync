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
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import requests
from bs4 import BeautifulSoup

# Google Calendar imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
GRADESCOPE_BASE_URL = "https://www.gradescope.com"


class GradescopeClient:
    """Client for interacting with Gradescope."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self._login()

    def _login(self):
        """Log into Gradescope."""
        # Get the login page to get CSRF token
        login_page = self.session.get(f"{GRADESCOPE_BASE_URL}/login")
        soup = BeautifulSoup(login_page.text, "html.parser")

        # Find CSRF token
        csrf_token = None
        csrf_input = soup.find("input", {"name": "authenticity_token"})
        if csrf_input:
            csrf_token = csrf_input.get("value")

        if not csrf_token:
            raise Exception("Could not find CSRF token on login page")

        # Perform login
        login_data = {
            "authenticity_token": csrf_token,
            "session[email]": self.email,
            "session[password]": self.password,
            "session[remember_me]": "0",
            "commit": "Log In",
            "session[remember_me_sso]": "0"
        }

        response = self.session.post(
            f"{GRADESCOPE_BASE_URL}/login",
            data=login_data,
            allow_redirects=True
        )

        # Check if login was successful by looking for courses page
        if "Invalid email/password combination" in response.text:
            raise Exception("Invalid credentials")

        if "/account" not in response.url and "/courses" not in response.text:
            raise Exception("Login failed - unexpected redirect")

    def get_courses(self) -> list:
        """Get all courses from the account page."""
        response = self.session.get(f"{GRADESCOPE_BASE_URL}/account")
        soup = BeautifulSoup(response.text, "html.parser")

        courses = []

        # Find all course links (new structure)
        for link in soup.find_all("a", href=re.compile(r"/courses/\d+")):
            href = link.get("href", "")
            course_id = href.split("/")[-1]

            # Get course name from the link content
            heading = link.find(["h3", "h4", "heading"])
            if heading:
                short_name = heading.get_text(strip=True)
            else:
                short_name = "Unknown Course"

            # Get full name
            name_div = link.find("div", class_=re.compile(r"courseBox--name|name"))
            full_name = name_div.get_text(strip=True) if name_div else short_name

            # Try to get assignment count
            count_div = link.find(string=re.compile(r"\d+ assignment"))

            courses.append({
                "id": course_id,
                "short_name": short_name,
                "full_name": full_name,
                "url": f"{GRADESCOPE_BASE_URL}{href}"
            })

        return courses

    def get_assignments(self, course_id: str) -> list:
        """Get all assignments for a course."""
        response = self.session.get(f"{GRADESCOPE_BASE_URL}/courses/{course_id}")
        soup = BeautifulSoup(response.text, "html.parser")

        assignments = []

        # Find assignment table rows
        for row in soup.find_all("tr", role="row"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 3:
                continue

            # First cell usually contains assignment name and link
            name_cell = cells[0]
            name_link = name_cell.find("a")

            if not name_link:
                continue

            name = name_link.get_text(strip=True)
            href = name_link.get("href", "")

            # Extract assignment ID from URL
            aid_match = re.search(r"/assignments/(\d+)", href)
            aid = aid_match.group(1) if aid_match else None

            # Try to find due date (usually in later cells)
            due_date = None
            for cell in cells[1:]:
                cell_text = cell.get_text(strip=True)
                # Look for date patterns
                if re.search(r"\d{1,2}:\d{2}", cell_text) or "due" in cell_text.lower():
                    due_date = cell_text
                    break

            # Also check for time element
            time_elem = row.find("time")
            if time_elem:
                due_date = time_elem.get("datetime") or time_elem.get_text(strip=True)

            assignments.append({
                "name": name,
                "id": aid,
                "due_date": due_date,
                "url": f"{GRADESCOPE_BASE_URL}{href}" if href else None
            })

        return assignments


class GoogleCalendarClient:
    """Client for interacting with Google Calendar."""

    def __init__(self, token_path: str = "token.json", credentials_path: str = "credentials.json"):
        self.token_path = Path(token_path)
        self.credentials_path = Path(credentials_path)
        self.service = self._get_service()

    def _get_service(self):
        """Get authenticated Google Calendar service."""
        creds = None

        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif self.credentials_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            else:
                raise Exception("No valid credentials found")

            # Save refreshed credentials
            with open(self.token_path, 'w') as f:
                f.write(creds.to_json())

        return build('calendar', 'v3', credentials=creds)

    def find_event(self, title: str, calendar_id: str = 'primary') -> Optional[dict]:
        """Find an existing event by title."""
        try:
            # Search for events with matching title
            events_result = self.service.events().list(
                calendarId=calendar_id,
                q=title,
                maxResults=10,
                singleEvents=True
            ).execute()

            events = events_result.get('items', [])
            for event in events:
                if event.get('summary') == title:
                    return event
        except Exception as e:
            print(f"Warning: Error searching for event: {e}")

        return None

    def create_or_update_event(self, title: str, due_date: str, description: str = "",
                               location: str = "", calendar_id: str = 'primary') -> dict:
        """Create or update a calendar event."""
        # Parse the due date
        event_datetime = self._parse_date(due_date)
        if not event_datetime:
            print(f"Warning: Could not parse date '{due_date}' for '{title}'")
            return None

        event_body = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': event_datetime.isoformat(),
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': event_datetime.isoformat(),
                'timeZone': 'America/Los_Angeles',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 60},
                    {'method': 'popup', 'minutes': 1440},  # 24 hours
                ],
            },
        }

        if location:
            event_body['location'] = location

        # Check if event already exists
        existing_event = self.find_event(title, calendar_id)

        if existing_event:
            # Update existing event
            event = self.service.events().update(
                calendarId=calendar_id,
                eventId=existing_event['id'],
                body=event_body
            ).execute()
            return {'action': 'updated', 'event': event}
        else:
            # Create new event
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            return {'action': 'created', 'event': event}

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from Gradescope."""
        if not date_str:
            return None

        # Common date formats from Gradescope
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone
            "%Y-%m-%dT%H:%M:%S",     # ISO format without timezone
            "%b %d, %Y %I:%M %p",    # "Jan 15, 2026 11:59 PM"
            "%b %d, %Y at %I:%M %p", # "Jan 15, 2026 at 11:59 PM"
            "%B %d, %Y %I:%M %p",    # "January 15, 2026 11:59 PM"
            "%m/%d/%Y %I:%M %p",     # "01/15/2026 11:59 PM"
            "%Y-%m-%d %H:%M:%S %z",  # "2026-01-15 23:59:00 -0800"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        # Try to extract datetime with regex
        patterns = [
            r"(\w+ \d+, \d{4} \d+:\d+ [AP]M)",
            r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                for fmt in formats:
                    try:
                        return datetime.strptime(match.group(1), fmt)
                    except ValueError:
                        continue

        return None


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
        # Connect to Gradescope
        print(f"Logging into Gradescope as {email}...")
        gs_client = GradescopeClient(email, password)
        print("Logged in successfully!")

        # Get courses
        print("Fetching courses...")
        courses = gs_client.get_courses()
        print(f"Found {len(courses)} courses")

        # Connect to Google Calendar
        print("Connecting to Google Calendar...")
        gcal_client = GoogleCalendarClient()

        # Process each course
        total_created = 0
        total_updated = 0
        total_skipped = 0

        for course in courses:
            print(f"\nProcessing: {course['short_name']} - {course['full_name']}")

            assignments = gs_client.get_assignments(course['id'])
            print(f"  Found {len(assignments)} assignments")

            for assignment in assignments:
                if not assignment['due_date']:
                    print(f"    Skipping '{assignment['name']}' - no due date")
                    total_skipped += 1
                    continue

                title = f"{assignment['name']} - {course['short_name']}"
                description = f"Course: {course['full_name']}\n"
                if assignment['url']:
                    description += f"Link: {assignment['url']}"

                result = gcal_client.create_or_update_event(
                    title=title,
                    due_date=assignment['due_date'],
                    description=description
                )

                if result:
                    if result['action'] == 'created':
                        print(f"    Created: {assignment['name']}")
                        total_created += 1
                    else:
                        print(f"    Updated: {assignment['name']}")
                        total_updated += 1
                else:
                    print(f"    Skipped '{assignment['name']}' - could not parse date")
                    total_skipped += 1

        print(f"\n{'='*50}")
        print("Sync completed!")
        print(f"  Created: {total_created}")
        print(f"  Updated: {total_updated}")
        print(f"  Skipped: {total_skipped}")
        print(f"{'='*50}")

    except Exception as e:
        print(f"ERROR: Sync failed - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
