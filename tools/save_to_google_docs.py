"""Save GrantPilot output to a formatted Google Doc.

Creates a Google Doc with three sections:
1. Funder Research Summary — extracted requirements, couldn't_determine flagged
2. Draft Sections — each labeled as a draft
3. Compliance Notes — what passed, what needs manual verification

Auth: OAuth2 desktop flow. On first run, opens a browser for Google login.
Saves the token to token.json so you don't have to re-login every time.
Handles token refresh automatically.

Requirements:
  pip install google-api-python-client google-auth google-auth-oauthlib
  - Google Cloud project with Docs API + Drive API enabled
  - OAuth consent screen configured and published (testing mode tokens
    expire after 7 days — published mode tokens last indefinitely)
  - OAuth client ID (Desktop app type) — download as client_secret.json
  - Optionally set GOOGLE_DRIVE_FOLDER_ID in .env to put docs in a folder
  - Optionally set GOOGLE_DOCS_SHARE_EMAIL in .env to auto-share
"""


import os
import json
import time
from pathlib import Path
import requests as http_requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


#auth

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

#token is saved next to client_secret.json (project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOKEN_PATH = _PROJECT_ROOT / "token.json"
_CLIENT_SECRET_PATH = _PROJECT_ROOT / "client_secret.json"


def _manual_flow_login():
    """OAuth2 flow for remote environments like Codespaces.

    Opens a Google sign-in URL. After granting access, the browser
    redirects to localhost which fails — but the authorization code
    is in the URL bar. User copies the full URL and pastes it back.
    """
    with open(_CLIENT_SECRET_PATH) as f:
        client_info = json.load(f)["installed"]

    client_id = client_info["client_id"]
    client_secret = client_info["client_secret"]
    redirect_uri = "http://localhost:8090"

    import urllib.parse
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        })
    )

    print(f"\n1. Open this URL in your browser:\n{auth_url}\n")
    print("2. Sign in and grant access.")
    print("3. You'll get a 'localhost refused to connect' error — that's expected.")
    print("4. Copy the ENTIRE URL from your browser's address bar.\n")

    redirect_url = input("Paste the full URL here: ")

    #pull the authorization code out of the URL
    parsed = urllib.parse.urlparse(redirect_url)
    code = urllib.parse.parse_qs(parsed.query)["code"][0]

    #exchange the code for tokens
    token_resp = http_requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    return Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def _load_client_config():
    """Load client config from env var (Render) or file (local dev)."""
    env_json = os.environ.get("GOOGLE_CLIENT_SECRET_JSON")
    if env_json:
        return json.loads(env_json)
    if _CLIENT_SECRET_PATH.exists():
        with open(_CLIENT_SECRET_PATH) as f:
            return json.load(f)
    raise FileNotFoundError(
        "No client secret found. Set GOOGLE_CLIENT_SECRET_JSON env var "
        "or place client_secret.json in the project root."
    )


def _get_credentials():
    """Load or create OAuth2 credentials with automatic refresh.

    Checks env vars first (for Render deployment where the filesystem
    is ephemeral), then falls back to files (for local dev).

    Flow:
    1. Try loading token from GOOGLE_TOKEN_JSON env var or token.json file.
    2. If the token is expired, refresh it automatically.
    3. If refresh fails or no token exists, run the manual OAuth flow
       (only works locally — Render uses the env var token).

    Returns:
        google.oauth2.credentials.Credentials
    """
    creds = None

    #1. try env var first (Render), then file (local)
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)

    #2. if no valid creds, either refresh or do full login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            # Full login — only works locally, not on Render
            _load_client_config()  # validate config exists before prompting
            creds = _manual_flow_login()

        #3. save for next time (local dev only — env var deployments
        #   refresh from the stored refresh token on each cold start)
        _TOKEN_PATH.write_text(creds.to_json())

    return creds


#document building helpers

#Google Docs batchUpdate works by inserting text at character indices and then applying formatting.  The simplest pattern for building a new doc:
#1. Build the full plain text and track where each "span" starts/ends.
#2. Insert all the text in one request.
#3. Apply paragraph styles (headings) and character styles (bold) as separate requests referencing the tracked indices.
#indices are 1-based (index 1 = start of the document body).


class _DocBuilder:
    """Accumulates text + formatting, then emits Google Docs API requests."""

    def __init__(self):
        self.text = ""
        self._heading_spans = []   #(start, end, heading_level)
        self._bold_spans = []      #(start, end)

    def _pos(self):
        """Current insertion index (1-based, accounting for text so far)."""
        return len(self.text) + 1

    def add_heading(self, text: str, level: int = 1):
        start = self._pos()
        self.text += text + "\n"
        end = self._pos()
        self._heading_spans.append((start, end - 1, level))

    def add_bold_line(self, text: str):
        start = self._pos()
        self.text += text
        end_bold = self._pos()
        self._bold_spans.append((start, end_bold - 1))
        self.text += "\n"

    def add_line(self, text: str = ""):
        self.text += text + "\n"

    def add_warning_line(self, text: str):
        """A bold line with >>> prefix — stands out visually."""
        start = self._pos()
        full = f">>> {text}"
        self.text += full + "\n"
        end = self._pos()
        self._bold_spans.append((start, end - 1))

    def build_requests(self) -> list[dict]:
        """Return the list of batchUpdate requests."""
        requests = []

        #1. insert all text at index 1
        requests.append({
            "insertText": {
                "location": {"index": 1},
                "text": self.text,
            }
        })

        #2. apply heading styles
        for start, end, level in self._heading_spans:
            heading_id = f"HEADING_{level}"
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": heading_id},
                    "fields": "namedStyleType",
                }
            })

        #3. apply bold
        for start, end in self._bold_spans:
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            })

        return requests


#content formatting

#labels for funder_reqs fields so the doc reads naturally.
FIELD_LABELS = {
    "funder_name": "Funder",
    "funder_overview": "Program Overview",
    "deadline": "Deadline",
    "funding_amount": "Funding Amount",
    "eligibility": "Eligibility Requirements",
    "page_word_limits": "Page / Word Limits",
    "required_sections": "Required Sections",
    "evaluation_criteria": "Evaluation Criteria",
    "past_funded_projects": "Past Funded Projects",
}


def _format_field_value(value) -> str:
    """Turn a funder_reqs value into readable text."""
    if value == "couldn't_determine":
        return "!!! VERIFY MANUALLY !!! — not found in source material"
    if isinstance(value, list):
        return "\n".join(f"  • {item}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"  • {k}: {v}" for k, v in value.items())
    return str(value)


def _build_funder_section(doc: _DocBuilder, funder_reqs: dict):
    """Section 1: Funder Research Summary."""
    doc.add_heading("Funder Research Summary", level=1)
    doc.add_line(
        "Everything the Research Agent found about this grant opportunity. "
        "Items marked !!! VERIFY MANUALLY !!! could not be determined from the "
        "source material — check the original RFP."
    )
    doc.add_line()

    for key, label in FIELD_LABELS.items():
        value = funder_reqs.get(key)
        if value is None:
            continue
        doc.add_bold_line(f"{label}:")
        doc.add_line(_format_field_value(value))
        doc.add_line()


def _build_drafts_section(doc: _DocBuilder, drafted_sections: dict):
    """Section 2: Draft Sections."""
    doc.add_heading("Draft Sections", level=1)
    doc.add_line(
        "Each section below is an AI-generated first draft. "
        "Edit freely — these are starting points, not finished text."
    )
    doc.add_line()

    #consistent display order
    section_order = [
        "project_narrative",
        "needs_statement",
        "goals_objectives",
        "evaluation_plan",
        "org_background",
        "budget_justification",
    ]

    #sections in the defined order first, then any extras
    ordered_keys = [k for k in section_order if k in drafted_sections]
    extras = [k for k in drafted_sections if k not in section_order]
    ordered_keys.extend(extras)

    for section_key in ordered_keys:
        section = drafted_sections[section_key]
        display_name = section_key.replace("_", " ").title()
        word_count = section.get("word_count", "?")

        doc.add_heading(
            f"DRAFT — {display_name}  ({word_count} words)", level=2
        )
        doc.add_line(section.get("content", "[No content]"))
        doc.add_line()


def _build_compliance_section(
    doc: _DocBuilder, compliance_report: dict, verify_manually: list
):
    """Section 3: Compliance Notes."""
    doc.add_heading("Compliance Notes", level=1)

    #overall status
    status = compliance_report.get("overall_status", "unknown")
    status_display = {
        "approved": "PASSED — All automated checks passed",
        "needs_revision": "ISSUES FOUND — see below",
        "max_revisions_reached": (
            "REVISION LIMIT REACHED — review issues below"
        ),
    }.get(status, status)
    doc.add_bold_line(f"Status: {status_display}")
    doc.add_line()

    #programmatic checks
    prog = compliance_report.get("programmatic_checks", {})
    deadline = prog.get("deadline")
    if deadline:
        doc.add_bold_line("Deadline:")
        doc.add_line(f"  {deadline}")
        doc.add_line()

    word_counts = prog.get("word_count", [])
    if word_counts:
        doc.add_bold_line("Word Count Checks:")
        for wc in word_counts:
            icon = "OK" if wc["status"] == "within_limit" else "OVER"
            doc.add_line(
                f"  {icon} {wc['section']}: {wc['word_count']} words "
                f"(limit: {wc['limit']})"
            )
        doc.add_line()

    #revision feedback (writer-fixable issues)
    feedback = compliance_report.get("revision_feedback", "")
    if feedback:
        doc.add_bold_line("Revision Notes:")
        doc.add_line(f"  {feedback}")
        doc.add_line()

    #verify manually applicant action items
    if verify_manually:
        doc.add_heading("Action Items — Verify Manually", level=2)
        doc.add_line(
            "These items require information the AI doesn't have. "
            "Check each one before submitting."
        )
        doc.add_line()
        for item in verify_manually:
            doc.add_warning_line(item)
    else:
        doc.add_line("No manual verification items.")


#main function


def save_to_google_docs(
    funder_reqs: dict,
    drafted_sections: dict,
    compliance_report: dict,
    verify_manually: list | None = None,
) -> str:
    """Save the final output to a Google Doc.

    Creates a formatted Google Doc with three sections:
    1. Funder Research Summary
    2. Draft Sections (labeled as drafts)
    3. Compliance Notes (what passed, what to verify)

    Args:
        funder_reqs: structured requirements from the Research Agent
        drafted_sections: dict of drafted section content
        compliance_report: final compliance check results
        verify_manually: items only the applicant can resolve
            (pulled from compliance_report if not passed separately)

    Returns:
        str: URL of the created Google Doc
    """
    if verify_manually is None:
        verify_manually = compliance_report.get("verify_manually", [])

    #authenticate
    creds = _get_credentials()
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    #create empty doc via Drive API (supports folder placement)
    funder_name = funder_reqs.get("funder_name", "Grant Opportunity")
    title = f"GrantPilot Draft — {funder_name}"
    create_body = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if folder_id:
        create_body["parents"] = [folder_id]

    doc = drive_service.files().create(body=create_body).execute()
    doc_id = doc["id"]

    #build content
    builder = _DocBuilder()
    _build_funder_section(builder, funder_reqs)
    _build_drafts_section(builder, drafted_sections)
    _build_compliance_section(builder, compliance_report, verify_manually)

    #write content to doc
    requests = builder.build_requests()
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    #share if email(s) configured (comma-separated)
    share_emails = os.environ.get("GOOGLE_DOCS_SHARE_EMAIL", "")
    for email in share_emails.split(","):
        email = email.strip()
        if email:
            drive_service.permissions().create(
                fileId=doc_id,
                body={
                    "type": "user",
                    "role": "writer",
                    "emailAddress": email,
                },
                sendNotificationEmail=True,
            ).execute()

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"\nGoogle Doc created: {doc_url}")
    return doc_url