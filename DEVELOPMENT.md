# Development Notes - Gradescope Calendar Sync

## Project Overview

Automatically syncs Gradescope assignments to Google Calendar (Berkeley Calendar) using GitHub Actions. Runs twice daily at 8 AM and 8 PM Pacific.

## Architecture

```
GitHub Actions (runs on schedule)
    │
    ├── Logs into Gradescope (email/password)
    ├── Scrapes assignment data from each course
    └── Creates/updates events in Google Calendar via API
```

## Key Files

| File | Purpose |
|------|---------|
| `sync_gradescope.py` | Main script - Gradescope scraper + Google Calendar integration |
| `.github/workflows/sync.yml` | GitHub Actions workflow (schedule, environment) |
| `setup_google_auth.py` | One-time script to generate Google OAuth token |
| `requirements.txt` | Python dependencies |
| `token.json` | Local Google OAuth token (not in repo) |
| `credentials.json` | Google Cloud OAuth client credentials (not in repo) |

## GitHub Secrets Required

| Secret | Value |
|--------|-------|
| `GRADESCOPE_EMAIL` | aryanvalsa@berkeley.edu |
| `GRADESCOPE_PASSWORD` | Gradescope direct login password |
| `GOOGLE_TOKEN` | Base64-encoded contents of token.json |

To update GOOGLE_TOKEN:
```bash
base64 -i token.json | pbcopy  # Copies to clipboard
# Then paste into GitHub Secrets
```

## Local Development

```bash
# Setup
cd /Users/aryan/Documents/CodeProjects/gradescope-calendar-sync
source venv/bin/activate
pip install -r requirements.txt

# Run sync
GRADESCOPE_EMAIL="aryanvalsa@berkeley.edu" GRADESCOPE_PASSWORD="yourpassword" python sync_gradescope.py

# Run cleanup (delete events from personal calendar)
python sync_gradescope.py --cleanup
```

## How the Gradescope Scraper Works

1. **Login**: POST to `/login` with CSRF token + credentials
2. **Get courses**: Parse `/account` page for course links (`/courses/{id}`)
3. **Get assignments**: For each course, parse the assignments table
   - Assignment names from `<a>` links or `<button data-assignment-title="...">`
   - Due dates from `<time class="submissionTimeChart--dueDate" datetime="...">`

## Common Issues & Fixes

### "Invalid credentials"
- User uses Berkeley SSO, not direct password
- Fix: Set a direct Gradescope password in Account Settings

### Wrong dates (release date instead of due date)
- Old code grabbed wrong column
- Fix: Use `<time class="submissionTimeChart--dueDate">` element's `datetime` attribute

### Missing assignments
- Some assignments have buttons (unsubmitted) instead of links
- Fix: Also check `<button data-assignment-title="...">` for assignment names

### Google token expired
- Re-run `setup_google_auth.py` locally
- Update `GOOGLE_TOKEN` secret with new base64-encoded token

## Gradescope Page Structure (as of Jan 2026)

```html
<!-- Course page assignment row -->
<tr role="row">
  <th>
    <a href="/courses/123/assignments/456/submissions/789">Assignment Name</a>
    <!-- OR for unsubmitted: -->
    <button data-assignment-title="Assignment Name" data-assignment-id="456">Submit</button>
  </th>
  <td>Submitted / No Submission</td>
  <td>
    <time class="submissionTimeChart--releaseDate" datetime="2026-01-20 12:00:00 -0800">Jan 20</time>
    <time class="submissionTimeChart--dueDate" datetime="2026-01-24 16:00:00 -0800">Jan 24 at 4:00PM</time>
  </td>
</tr>
```

## Google Calendar Setup

1. Google Cloud Console: https://console.cloud.google.com/
2. Project: "Gradescope Calendar Sync"
3. API: Google Calendar API (enabled)
4. OAuth consent screen: Internal (berkeley.edu)
5. Credentials: OAuth 2.0 Desktop App

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRADESCOPE_EMAIL` | (required) | Gradescope login email |
| `GRADESCOPE_PASSWORD` | (required) | Gradescope direct password |
| `GOOGLE_TOKEN` | (optional) | Base64 token for GitHub Actions |
| `GOOGLE_CALENDAR_NAME` | "Berkeley Calendar" | Target calendar name |

## Cron Schedule

Current: `0 4,16 * * *` (8 AM and 8 PM Pacific in UTC)

- GitHub Actions uses UTC
- 8 AM Pacific = 16:00 UTC (PST) / 15:00 UTC (PDT)
- 8 PM Pacific = 04:00 UTC (PST) / 03:00 UTC (PDT)

## If Gradescope Changes Their Website

1. Log into Gradescope in browser
2. Inspect the assignments table structure
3. Update `get_assignments()` method in `sync_gradescope.py`
4. Key things to find:
   - How assignment names are displayed
   - Where the due date is stored (look for `<time>` elements)
   - Any new class names or data attributes

## Repository

- GitHub: https://github.com/CoolKingGreat/gradescope-calendar-sync
- Visibility: Private
- Owner: CoolKingGreat
