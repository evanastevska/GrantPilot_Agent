"""GrantPilot Flask app - single-page UI for grant research and drafting."""

import os
import uuid
import hashlib
import threading
import json

from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

load_dotenv()

#import the compiled LangGraph (renamed to avoid conflict with Flask app)
from graph import app as grant_graph

flask_app = Flask(__name__)
flask_app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

#password stored as SHA-256 hash in .env
#generate with: python -c 'import hashlib; print(hashlib.sha256(b"your-password").hexdigest())'
APP_PASSWORD_HASH = os.environ.get("APP_PASSWORD_HASH", "")

#in-memory job store, fine for 1-2 users
jobs = {}


def _step_labels(node_name, accumulated):
    """Return (spinner_label, done_label) based on node and revision count."""
    rev = accumulated.get("revision_count", 0)

    if node_name == "research_node":
        return ("Researching funder requirements...", "Researched funder requirements")
    elif node_name == "writing_node":
        if rev >= 1:
            return ("Revising drafts...", "Revised drafts")
        return ("Drafting sections...", "Drafted sections")
    elif node_name == "review_node":
        if rev >= 2:
            return ("Rechecking compliance...", "Rechecked compliance")
        return ("Checking compliance...", "Checked compliance")
    elif node_name == "save_docs_node":
        return ("Saving to Google Docs...", "Saved to Google Docs")
    return (node_name, node_name)


def run_graph_job(job_id, funder_url, raw_grant_text):
    """Run the full LangGraph pipeline in a background thread."""
    try:
        initial_state = {
            "funder_url": funder_url,
            "raw_grant_text": raw_grant_text,
            "funder_reqs": {},
            "org_profile": {},
            "drafted_sections": {},
            "compliance_report": {},
            "revision_feedback": "",
            "revision_count": 0,
            "status": "researching",
            "verify_manually": [],
            "doc_url": "",
        }

        accumulated = dict(initial_state)

        for chunk in grant_graph.stream(initial_state):
            node_name = list(chunk.keys())[0]
            node_output = chunk[node_name]
            accumulated.update(node_output)

            spinner, done = _step_labels(node_name, accumulated)
            jobs[job_id]["current_step"] = spinner
            jobs[job_id]["steps_completed"].append(done)

            #capture review loop info for the activity log
            if node_name == "review_node":
                jobs[job_id]["activity_log"].append({
                    "loop": accumulated.get("revision_count", 0),
                    "status": node_output.get("compliance_report", {}).get(
                        "overall_status", ""
                    ),
                    "feedback": node_output.get("revision_feedback", ""),
                    "revision_type": node_output.get("compliance_report", {}).get(
                        "revision_type", ""
                    ),
                })

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["result"] = accumulated

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@flask_app.route("/")
def index():
    return render_template("index.html")


@flask_app.route("/login", methods=["POST"])
def login():
    password = request.json.get("password", "")
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    if password_hash == APP_PASSWORD_HASH:
        session["authenticated"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Incorrect password."}), 401


@flask_app.route("/generate", methods=["POST"])
def generate():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated."}), 401

    data = request.json
    funder_url = data.get("funder_url", "").strip()
    raw_grant_text = data.get("raw_grant_text", "").strip()

    if not funder_url and not raw_grant_text:
        return jsonify({
            "error": "Provide grant requirements text or a funder URL (or both)."
        }), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "current_step": "Starting...",
        "steps_completed": [],
        "activity_log": [],
        "result": None,
        "error": None,
    }

    thread = threading.Thread(
        target=run_graph_job,
        args=(job_id, funder_url, raw_grant_text),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@flask_app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404

    response = {
        "status": job["status"],
        "current_step": job["current_step"],
        "steps_completed": job["steps_completed"],
    }

    if job["status"] == "complete":
        result = job["result"]
        response["doc_url"] = result.get("doc_url", "")
        response["final_status"] = result.get("status", "")
        response["verify_manually"] = result.get("verify_manually", [])
        response["revision_count"] = result.get("revision_count", 0)
        response["activity_log"] = job["activity_log"]

        #key funder fields for the summary card
        funder = result.get("funder_reqs", {})
        response["funder_summary"] = {
            "funder_name": funder.get("funder_name", ""),
            "deadline": funder.get("deadline", ""),
            "funding_amount": funder.get("funding_amount", ""),
            "eligibility": funder.get("eligibility", ""),
            "required_sections": funder.get("required_sections", ""),
            "evaluation_criteria": funder.get("evaluation_criteria", ""),
        }

    if job["status"] == "error":
        response["error"] = job["error"]

    return jsonify(response)


if __name__ == "__main__":
    flask_app.run(debug=True, port=5000)