"""Microsoft Graph API client wrapper."""

import os
import re
from datetime import datetime, timedelta, timezone

import httpx

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class MSGraphClient:
    """Thin async wrapper around Microsoft Graph API using httpx."""

    def __init__(self, access_token: str):
        self._token = access_token
        self._headers = {"Authorization": f"Bearer {access_token}"}
        # Temporary patch: pass simulation ID to veris mock services
        sim_id = os.environ.get("SIMULATION_ID")
        if sim_id:
            self._headers["X-Veris-Session-Id"] = sim_id

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_BASE}{path}",
                headers=self._headers,
                params=params,
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp

    async def list_recent_meetings(self, days_back: int = 7) -> list[dict]:
        """List recent online meetings from the user's calendar."""
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        params = {
            "$filter": f"start/dateTime ge '{since}'",
            "$orderby": "start/dateTime desc",
            "$top": "50",
            "$select": "id,subject,start,end,isOnlineMeeting,onlineMeeting",
        }
        resp = await self._get("/me/events", params=params)
        events = resp.json().get("value", [])
        # Filter to online meetings client-side (Graph doesn't support filtering on isOnlineMeeting)
        return [e for e in events if e.get("isOnlineMeeting")]

    async def list_transcripts(self, meeting_id: str) -> list[dict]:
        """List transcripts for an online meeting."""
        resp = await self._get(f"/me/onlineMeetings/{meeting_id}/transcripts")
        return resp.json().get("value", [])

    async def get_transcript_content(
        self, meeting_id: str, transcript_id: str
    ) -> str:
        """Download transcript content as VTT text."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content",
                headers={**self._headers, "Accept": "text/vtt"},
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.text

    async def list_onedrive_files(self, folder_path: str = "/") -> list[dict]:
        """List files in a OneDrive folder."""
        if folder_path == "/":
            path = "/me/drive/root/children"
        else:
            clean = folder_path.strip("/")
            path = f"/me/drive/root:/{clean}:/children"
        resp = await self._get(path)
        return resp.json().get("value", [])

    async def get_file_content(self, item_id: str) -> bytes:
        """Download file content from OneDrive."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/drive/items/{item_id}/content",
                headers=self._headers,
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def parse_vtt(vtt_text: str) -> str:
        """Strip VTT timestamps and formatting, return plain speaker: text."""
        lines = vtt_text.splitlines()
        result = []
        for line in lines:
            line = line.strip()
            # Skip WEBVTT header, blank lines, sequence numbers, timestamps
            if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                continue
            if re.match(r"^\d+$", line):
                continue
            if re.match(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", line):
                continue
            # Strip VTT tags like <v Speaker Name>
            line = re.sub(r"<v\s+([^>]+)>", r"\1: ", line)
            line = re.sub(r"</v>", "", line)
            result.append(line)
        return "\n".join(result)
