# Trustworthy Model Registry

## Quick start
### Set up virtual environment and install dependencies
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Set up environment variables
- `LOG_FILE` - Name of the log file
- `LOG_VERBOSITY` - Verbosity of logging (0 - silent, 1 - INFO, 2 - DEBUG)
- `GITHUB_TOKEN` - Your GitHub token
- `GEN_AI_STUDIO_API_KEY` - Purdue GenAI Studio API key 

Note: You can obtain the `GEN_AI_STUDIO_API_KEY` at https://genai.rcac.purdue.edu/ by logging in to your Purdue student account, click on your profile -> Settings -> Account -> API Keys and then create one.

### Run API server

```run api```

### Run frontend locally
In order to run the frontend locally (for testing), run the following command in the `frontend` directory:
```
npm run dev
```
