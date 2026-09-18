# Part 1 security setup

## Credentials

The runtime reads `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from the process environment only. `config/api_keys.json` remains ignored for non-secret preferences, but provider keys in that file are no longer accepted. Rotate any key that was ever committed or shared:

```powershell
$env:GEMINI_API_KEY = "<new-key>"
python -m pip install git-filter-repo
git filter-repo --path config/api_keys.json --invert-paths
git push --force-with-lease --all
```

Coordinate history rewriting with every clone and revoke the old provider key before rewriting history. Enable GitHub secret scanning and a Gitleaks pre-commit/CI check before publishing again.

## Security boundary

Remote dashboard commands are authenticated by short-lived in-memory bearer tokens, rate limited, schema checked, and destructive tool calls require an explicit approval workflow. Prompts and model output are redacted before UI logs and transcripts. Run the dashboard over the generated TLS certificate when connecting from another device.

## Validation

```powershell
python -m pytest
python -m compileall main.py security dashboard
```
