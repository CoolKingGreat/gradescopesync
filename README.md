# Gradescope to Google Calendar Sync

Automatically sync your Gradescope assignments to Google Calendar using GitHub Actions.

## Features

- Runs automatically every 2 hours (even when your laptop is off)
- Prevents duplicate calendar events
- Updates existing events when due dates change
- Secure credential storage via GitHub Secrets

## Setup Instructions

### 1. Set Up Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Search for "Google Calendar API" and enable it
4. Go to **APIs & Services > Credentials**
5. Click **Create Credentials > OAuth client ID**
6. Select **Desktop application** as the application type
7. Download the JSON file and save it as `credentials.json` in this directory

### 2. Generate Google OAuth Token

Run the setup script locally (one-time only):

```bash
pip install -r requirements.txt
python setup_google_auth.py
```

This will open a browser for Google authentication and create `token.json`.

### 3. Encode Token for GitHub

On macOS:
```bash
base64 -i token.json | pbcopy
```

On Linux:
```bash
base64 -w 0 token.json
```

Copy the output for the next step.

### 4. Configure GitHub Secrets

Go to your repository's **Settings > Secrets and variables > Actions** and add:

| Secret Name | Value |
|-------------|-------|
| `GRADESCOPE_EMAIL` | Your Gradescope email address |
| `GRADESCOPE_PASSWORD` | Your Gradescope password |
| `GOOGLE_TOKEN` | The base64-encoded token from step 3 |

### 5. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Gradescope calendar sync"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/gradescope-calendar-sync.git
git push -u origin main
```

### 6. Verify It Works

1. Go to your repository on GitHub
2. Click **Actions** tab
3. Click **Sync Gradescope to Google Calendar**
4. Click **Run workflow** to trigger a manual sync
5. Check your Google Calendar for the assignments

## Local Testing

To run the sync locally:

```bash
export GRADESCOPE_EMAIL="your-email@example.com"
export GRADESCOPE_PASSWORD="your-password"
python sync_gradescope.py
```

## Troubleshooting

### "No Google credentials found"
Run `python setup_google_auth.py` to generate the token.

### "Missing Gradescope credentials"
Make sure `GRADESCOPE_EMAIL` and `GRADESCOPE_PASSWORD` are set (either as environment variables locally or as GitHub Secrets).

### GitHub Actions workflow not running
- Check that secrets are configured correctly
- Verify the workflow file is in `.github/workflows/`
- Try triggering manually from the Actions tab

### Token expired
Google OAuth tokens can expire. If syncs start failing:
1. Run `setup_google_auth.py` locally again
2. Re-encode and update the `GOOGLE_TOKEN` secret

## Schedule

The sync runs automatically every 2 hours via GitHub Actions. You can modify the schedule in `.github/workflows/sync.yml`:

```yaml
schedule:
  - cron: '0 */2 * * *'  # Every 2 hours
  # - cron: '0 * * * *'  # Every hour
  # - cron: '0 8,12,18 * * *'  # At 8am, 12pm, and 6pm
```

## Security

- All credentials are stored as encrypted GitHub Secrets
- Credentials are never logged or exposed in workflow runs
- Use a private repository for additional security

## Credits

- [gradescopecalendar](https://pypi.org/project/gradescopecalendar/) - Python package for Gradescope integration
