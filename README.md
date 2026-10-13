# Mini GitHub Clone

A local repository browser with account sessions, repository creation, text/source file upload, and source browsing. SQLite stores repositories and content. Any local visitor can browse repos; only a repo owner can create/update files.

## Run
Python 3.10+, no packages required. Run `python app.py`; open http://127.0.0.1:8000. SQLite data is generated in ignored `data/`.

## Safety limits
Educational loopback-only clone, not a Git server and not suitable for public hosting. File paths reject absolute paths, invalid segments, and traversal (`..`); file content is UTF-8 text, max 50 KB, limited to common text/source extensions. Files live in SQLite and are never executed or written to an executable path. Do not upload secrets or personal data.

## Tests
`python -m unittest discover -s tests -v`
