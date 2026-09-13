# Limitations and integration requirements

Nested extractor entries, output files and the download route were checked with synthetic extractor responses. A live YouTube extraction was not run.

The local requirements include Flask and yt-dlp. Public content needs no API key; live extraction depends on YouTube and the installed extractor version.

Keep web services bound to `127.0.0.1`. Hosting this application for multiple users requires authentication and separate storage and resource limits.
