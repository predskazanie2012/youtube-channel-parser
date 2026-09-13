# YouTube Channel Parser

YouTube Channel Parser turns a channel URL into a reusable list of video links. A local web form manages collection progress and delivers a text export for research, planning and later media processing.

## Features

- Accept a channel URL through a local web form.
- Extract video links and available metadata with yt-dlp.
- Show progress during collection.
- Export structured results for downstream processing.

## How it works

A reusable parser module performs channel extraction; the Flask interface manages jobs and result delivery.

**Stack:** Python · Flask · yt-dlp

## Getting started

Use Python 3.12 and a separate virtual environment. Run the following commands from this repository's root in Windows PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-local.txt
```

The local requirements include Flask and yt-dlp. Public content needs no API key; live extraction depends on YouTube and the installed extractor version.

### Start the application

Use the local URL printed in the terminal. No API key is required for public content; extractor behavior depends on YouTube and the installed yt-dlp version.

```powershell
python app.py
```

## Example workflow

Enter a permitted public channel URL, collect its videos, and download the text list.

## Testing and limitations

Nested extractor entries, output files and the download route were checked with synthetic extractor responses. A live YouTube extraction was not run.

See [Verification](VERIFICATION.md) for the recorded checks and [Limitations](LIMITATIONS.md) for integration requirements.

## Configuration and security

Keep web services bound to `127.0.0.1`. Hosting this application for multiple users requires authentication and separate storage and resource limits. Configure your own provider credentials when a feature requires them; credentials and personal data are not included. See [Security](SECURITY.md) for local configuration and reporting guidance.
