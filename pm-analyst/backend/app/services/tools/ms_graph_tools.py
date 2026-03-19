"""ADK agent tools for Microsoft Graph — meetings, transcripts, OneDrive."""

import io
import logging

import httpx

from app.services.ms_graph import MSGraphClient

logger = logging.getLogger(__name__)

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"}


def _get_graph_client(tool_context) -> MSGraphClient:
    token = tool_context.state.get("ms_access_token")
    if not token:
        raise ValueError(
            "Not authenticated with Microsoft. "
            "Please sign in first at /auth/microsoft/login"
        )
    return MSGraphClient(token)


async def list_recent_meetings(tool_context) -> dict:
    """List the user's recent Teams meetings that may have transcripts.

    Returns a list of recent online meetings with their IDs, subjects, and dates.
    Use the onlineMeeting joinWebUrl to get the meeting ID for transcript lookups.
    """
    try:
        client = _get_graph_client(tool_context)
        meetings = await client.list_recent_meetings()
    except httpx.HTTPStatusError as e:
        logger.error("Graph API error listing meetings: %s %s", e.response.status_code, e.response.text)
        return {"error": f"Microsoft Graph API error: {e.response.status_code}. Your tenant may not have an Exchange Online / Microsoft 365 license."}

    results = []
    for m in meetings:
        online_meeting = m.get("onlineMeeting") or {}
        results.append({
            "id": m["id"],
            "subject": m.get("subject", "(no subject)"),
            "start": m.get("start", {}).get("dateTime", ""),
            "end": m.get("end", {}).get("dateTime", ""),
            "join_url": online_meeting.get("joinUrl", ""),
        })

    return {"meetings": results, "count": len(results)}


async def get_meeting_transcript(meeting_id: str, tool_context) -> dict:
    """Fetch and parse the transcript for a specific Teams meeting.

    Args:
        meeting_id: The online meeting ID to fetch the transcript for.

    Returns the parsed plain-text transcript with speaker names.
    """
    try:
        client = _get_graph_client(tool_context)
        transcripts = await client.list_transcripts(meeting_id)
    except httpx.HTTPStatusError as e:
        return {"error": f"Microsoft Graph API error: {e.response.status_code}. Could not fetch transcripts."}

    if not transcripts:
        return {"error": "No transcripts found for this meeting."}

    transcript_id = transcripts[0]["id"]
    try:
        vtt_text = await client.get_transcript_content(meeting_id, transcript_id)
    except httpx.HTTPStatusError as e:
        return {"error": f"Microsoft Graph API error: {e.response.status_code}. Could not download transcript content."}

    parsed = MSGraphClient.parse_vtt(vtt_text)

    return {
        "transcript_id": transcript_id,
        "content": parsed,
        "format": "plain_text",
    }


async def list_onedrive_files(folder_path: str, tool_context) -> dict:
    """List files and folders in the user's OneDrive.

    Args:
        folder_path: The folder path to list (use "/" for root).

    Returns a list of files and folders with names, sizes, and IDs.
    """
    try:
        client = _get_graph_client(tool_context)
        items = await client.list_onedrive_files(folder_path)
    except httpx.HTTPStatusError as e:
        return {"error": f"Microsoft Graph API error: {e.response.status_code}. Your tenant may not have a OneDrive / Microsoft 365 license."}

    results = []
    for item in items:
        entry = {
            "id": item["id"],
            "name": item.get("name", ""),
            "size": item.get("size", 0),
            "type": "folder" if "folder" in item else "file",
        }
        if "file" in item:
            entry["mime_type"] = item["file"].get("mimeType", "")
        if "lastModifiedDateTime" in item:
            entry["modified"] = item["lastModifiedDateTime"]
        results.append(entry)

    return {"items": results, "count": len(results), "folder": folder_path}


async def get_onedrive_file(item_id: str, tool_context) -> dict:
    """Download and return the text content of a OneDrive file.

    Args:
        item_id: The OneDrive item ID of the file to download.

    Supports .txt, .md, .csv, .json, .xml, .html, and .docx files.
    """
    try:
        client = _get_graph_client(tool_context)
        resp = await client._get(f"/me/drive/items/{item_id}")
    except httpx.HTTPStatusError as e:
        return {"error": f"Microsoft Graph API error: {e.response.status_code}. Could not access file."}

    metadata = resp.json()
    name = metadata.get("name", "")

    ext = ""
    if "." in name:
        ext = "." + name.rsplit(".", 1)[1].lower()

    if ext == ".docx":
        try:
            from docx import Document
            content_bytes = await client.get_file_content(item_id)
            doc = Document(io.BytesIO(content_bytes))
            text = "\n".join(p.text for p in doc.paragraphs if p.text)
            return {"name": name, "content": text, "size": len(content_bytes)}
        except httpx.HTTPStatusError as e:
            return {"error": f"Microsoft Graph API error: {e.response.status_code}. Could not download file content."}
        except Exception as e:
            logger.error("Failed to parse .docx %s: %s", name, e)
            return {"error": f"Failed to extract text from {name}: {e}"}

    if ext in (".pdf", ".pptx", ".xlsx"):
        return {
            "error": f"Text extraction for {ext} files is not supported yet. "
            f"File: {name}",
        }

    if ext not in SUPPORTED_TEXT_EXTENSIONS:
        return {
            "error": f"Unsupported file type: {ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_TEXT_EXTENSIONS))}",
        }

    try:
        content_bytes = await client.get_file_content(item_id)
    except httpx.HTTPStatusError as e:
        return {"error": f"Microsoft Graph API error: {e.response.status_code}. Could not download file content."}

    text = content_bytes.decode("utf-8", errors="replace")

    return {
        "name": name,
        "content": text,
        "size": len(content_bytes),
    }
