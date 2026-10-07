from dotenv import load_dotenv
load_dotenv()
from tools.save_to_google_docs import _get_credentials
from googleapiclient.discovery import build

creds = _get_credentials()
drive = build("drive", "v3", credentials=creds)

doc = drive.files().create(
    body={
        "name": "Test Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
).execute()
print("Doc created via Drive:", doc["id"])

# now test if Docs API can WRITE to it
docs = build("docs", "v1", credentials=creds)
docs.documents().batchUpdate(
    documentId=doc["id"],
    body={"requests": [{"insertText": {"location": {"index": 1}, "text": "Hello world\n"}}]},
).execute()
print("Content written successfully")