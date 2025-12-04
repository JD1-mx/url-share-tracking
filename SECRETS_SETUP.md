# Secrets Management Setup Guide

This guide explains how to securely configure API keys for the Vehicle Tracking System.

## Overview

The app uses Streamlit's native secrets management to securely store the Tenderd API key. This prevents committing sensitive credentials to version control.

## Local Development Setup

### Option 1: Using Streamlit Secrets (Recommended)

1. **Create the secrets file** (if it doesn't exist):
   ```bash
   mkdir -p .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. **Edit `.streamlit/secrets.toml`** and add your API key:
   ```toml
   # Tenderd API Key
   TENDERD_API_KEY = "your_actual_api_key_here"
   ```

3. **Verify it's in .gitignore**:
   The `.streamlit/secrets.toml` file is already added to `.gitignore` to prevent accidental commits.

4. **Restart the app** if it's already running:
   ```bash
   # Stop the current app (Ctrl+C)
   # Then restart
   streamlit run app.py
   ```

### Option 2: Using Environment Variables

Alternatively, you can set the API key as an environment variable:

**macOS/Linux:**
```bash
export TENDERD_API_KEY="your_actual_api_key_here"
streamlit run app.py
```

**Windows (Command Prompt):**
```cmd
set TENDERD_API_KEY=your_actual_api_key_here
streamlit run app.py
```

**Windows (PowerShell):**
```powershell
$env:TENDERD_API_KEY="your_actual_api_key_here"
streamlit run app.py
```

## Deployment to Streamlit Community Cloud

When deploying to Streamlit Community Cloud:

1. **Go to your app's settings** in the Streamlit Cloud dashboard

2. **Navigate to the "Secrets" section**

3. **Add your secrets** in TOML format:
   ```toml
   TENDERD_API_KEY = "your_actual_api_key_here"
   ```

4. **Save** and the app will automatically restart with the new secrets

## Security Best Practices

### ✅ DO:
- Store secrets in `.streamlit/secrets.toml` for local development
- Use Streamlit Cloud's Secrets Management for deployed apps
- Keep `.streamlit/secrets.toml` in `.gitignore`
- Use `.streamlit/secrets.toml.example` as a template (without real values)

### ❌ DON'T:
- Commit `.streamlit/secrets.toml` to version control
- Hardcode API keys directly in the code
- Share your secrets file with others
- Push secrets to public repositories

## Troubleshooting

### Error: "TENDERD_API_KEY not found"

This error means the app can't find your API key. To fix:

1. **Check if secrets file exists**:
   ```bash
   ls -la .streamlit/secrets.toml
   ```

2. **Verify the content** (make sure `TENDERD_API_KEY` is set):
   ```bash
   cat .streamlit/secrets.toml
   ```

3. **Restart the Streamlit app** after creating/updating secrets

4. **Check for typos** in the key name (must be exactly `TENDERD_API_KEY`)

### Error: "FileNotFoundError" or "KeyError"

- **FileNotFoundError**: The `.streamlit/secrets.toml` file doesn't exist
  - Solution: Create the file using the template

- **KeyError**: The `TENDERD_API_KEY` key is missing or misspelled
  - Solution: Add the key exactly as shown above

## Getting Your API Key

1. Log in to your Tenderd account dashboard
2. Navigate to API settings or developer section
3. Generate or copy your API key
4. Paste it into your secrets configuration

## Example secrets.toml

```toml
# This is what your .streamlit/secrets.toml should look like

# Tenderd API Key (replace with your actual key)
TENDERD_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# You can add other secrets here if needed
# For example:
# DATABASE_URL = "postgresql://..."
# OTHER_API_KEY = "xyz123"
```

## Additional Resources

- [Streamlit Secrets Management Documentation](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [Streamlit Community Cloud Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
