"""Save GrantPilot output to a formatted Google Doc.

Creates a Google Doc with three sections:
1. Funder Research Summary — extracted requirements, couldn't_determine flagged
2. Draft Sections — each labeled as a draft
3. Compliance Notes — what passed, what needs manual verification

Auth: uses a service account JSON key (GOOGLE_SERVICE_ACCOUNT_FILE env var).
The doc is created in the service account's Drive and shared with
GOOGLE_DOCS_SHARE_EMAIL if set.

Requirements:
  pip install google-api-python-client google-auth
  - Google Cloud project with Docs API + Drive API enabled
  - Service account key JSON downloaded
  - Set GOOGLE_SERVICE_ACCOUNT_FILE=path/to/key.json in .env
  - Optionally set GOOGLE_DOCS_SHARE_EMAIL=trish@example.com
"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build


# ---------- auth ----------

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials():
    """Load service account credentials from the JSON key file."""
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sa_file:
        raise EnvironmentError(
            "Set GOOGLE_SERVICE_ACCOUNT_FILE to the path of your "
            "service account JSON key."
        )
    return service_account.Credentials.from_service_account_file(
        sa_file, scopes=SCOPES
    )


# ---------- document building helpers ----------

# Google Docs batchUpdate works by inserting text at character indices and
# then applying formatting.  The simplest pattern for building a new doc:
#   1. Build the full plain text and track where each "span" starts/ends.
#   2. Insert all the text in one request.
#   3. Apply paragraph styles (headings) and character styles (bold) as
#      separate requests referencing the tracked indices.
#
# Indices are 1-based (index 1 = start of the document body).


class _DocBuilder:
    """Accumulates text + formatting, then emits Google Docs API requests."""

    def __init__(self):
        self.text = ""
        self._heading_spans = []   # (start, end, heading_level)
        self._bold_spans = []      # (start, end)

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

        # 1. Insert all text at index 1
        requests.append({
            "insertText": {
                "location": {"index": 1},
                "text": self.text,
            }
        })

        # 2. Apply heading styles
        for start, end, level in self._heading_spans:
            heading_id = f"HEADING_{level}"
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": heading_id},
                    "fields": "namedStyleType",
                }
            })

        # 3. Apply bold
        for start, end in self._bold_spans:
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            })

        return requests


# ---------- content formatting ----------

# Labels for funder_reqs fields so the doc reads naturally.
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

    # Consistent display order
    section_order = [
        "project_narrative",
        "needs_statement",
        "goals_objectives",
        "evaluation_plan",
        "org_background",
        "budget_justification",
    ]

    # Sections in the defined order first, then any extras
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

    # Overall status
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

    # Programmatic checks
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

    # Revision feedback (writer-fixable issues)
    feedback = compliance_report.get("revision_feedback", "")
    if feedback:
        doc.add_bold_line("Revision Notes:")
        doc.add_line(f"  {feedback}")
        doc.add_line()

    # Verify manually — applicant action items
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


# ---------- main function ----------


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

    # --- authenticate ---
    creds = _get_credentials()
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # --- create empty doc ---
    funder_name = funder_reqs.get("funder_name", "Grant Opportunity")
    title = f"GrantPilot Draft — {funder_name}"
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    create_body = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        create_body["parents"] = [folder_id]

    doc = drive_service.files().create(body=create_body).execute()
    doc_id = doc["id"]

    # --- build content ---
    builder = _DocBuilder()
    _build_funder_section(builder, funder_reqs)
    _build_drafts_section(builder, drafted_sections)
    _build_compliance_section(builder, compliance_report, verify_manually)

    # --- write content to doc ---
    requests = builder.build_requests()
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    # --- share if an email is configured ---
    # new: shares to multiple
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
