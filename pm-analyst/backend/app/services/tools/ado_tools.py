"""ADK agent tools for Azure DevOps — work item CRUD with hierarchy."""

import logging

from app.config import get_settings
from app.services.ado_client import ADOClient

logger = logging.getLogger(__name__)

PARENT_REL = "System.LinkTypes.Hierarchy-Reverse"
CHILD_REL = "System.LinkTypes.Hierarchy-Forward"


def _get_ado_client(tool_context) -> ADOClient:
    token = tool_context.state.get("ado_access_token")
    if not token:
        raise ValueError(
            "Not authenticated with Azure DevOps. "
            "Please sign out and sign in again at /auth/microsoft/login"
        )
    settings = get_settings()
    if not settings.ado_org or not settings.ado_project:
        raise ValueError(
            "Azure DevOps is not configured. "
            "Set ADO_ORG and ADO_PROJECT in your .env file."
        )
    return ADOClient(token, settings.ado_org, settings.ado_project)


def _parse_relations(relations: list[dict] | None) -> dict:
    """Extract parent_id and child_ids from work item relations."""
    parent_id = 0
    child_ids = []
    for rel in relations or []:
        url = rel.get("url", "")
        rel_type = rel.get("rel", "")
        # Extract the ID from the URL (last segment)
        item_id_str = url.rsplit("/", 1)[-1] if "/" in url else ""
        if not item_id_str.isdigit():
            continue
        item_id = int(item_id_str)
        if rel_type == PARENT_REL:
            parent_id = item_id
        elif rel_type == CHILD_REL:
            child_ids.append(item_id)
    return {"parent_id": parent_id, "child_ids": child_ids}


def _format_work_item(raw: dict) -> dict:
    """Format a raw ADO work item response into a clean dict."""
    fields = raw.get("fields", {})
    hierarchy = _parse_relations(raw.get("relations"))
    return {
        "id": raw["id"],
        "type": fields.get("System.WorkItemType", ""),
        "title": fields.get("System.Title", ""),
        "state": fields.get("System.State", ""),
        "description": fields.get("System.Description", ""),
        "parent_id": hierarchy["parent_id"],
        "child_ids": hierarchy["child_ids"],
        "url": raw.get("_links", {}).get("html", {}).get("href", ""),
    }


async def create_work_item(
    work_item_type: str,
    title: str,
    description: str,
    parent_id: int,
    tool_context,
) -> dict:
    """Create a work item in Azure DevOps.

    Args:
        work_item_type: The type — "Epic", "Feature", or "User Story".
        title: The work item title.
        description: The work item description (plain text or HTML).
        parent_id: Parent work item ID to link under. Use 0 for no parent.

    Returns the created work item with id, type, title, state, and url.
    """
    client = _get_ado_client(tool_context)
    raw = await client.create_work_item(
        work_item_type, title, description, parent_id
    )
    # Fetch again with relations expanded for a complete response
    full = await client.get_work_item(raw["id"])
    return _format_work_item(full)


async def get_work_item(item_id: int, tool_context) -> dict:
    """Get a work item from Azure DevOps by ID.

    Args:
        item_id: The numeric work item ID.

    Returns the work item fields, parent_id, and child_ids.
    """
    client = _get_ado_client(tool_context)
    raw = await client.get_work_item(item_id)
    return _format_work_item(raw)


async def update_work_item(
    item_id: int,
    title: str,
    description: str,
    state: str,
    tool_context,
) -> dict:
    """Update a work item's title, description, or state in Azure DevOps.

    Args:
        item_id: The numeric work item ID to update.
        title: New title. Use empty string "" to leave unchanged.
        description: New description. Use empty string "" to leave unchanged.
        state: New state (e.g. "New", "Active", "Closed"). Use empty string "" to leave unchanged.

    Returns the updated work item.
    """
    client = _get_ado_client(tool_context)
    ops = []
    if title:
        ops.append({
            "op": "replace",
            "path": "/fields/System.Title",
            "value": title,
        })
    if description:
        ops.append({
            "op": "replace",
            "path": "/fields/System.Description",
            "value": description,
        })
    if state:
        ops.append({
            "op": "replace",
            "path": "/fields/System.State",
            "value": state,
        })
    if not ops:
        return {"error": "No fields to update. Provide at least one of: title, description, state."}
    raw = await client.update_work_item(item_id, ops)
    full = await client.get_work_item(raw["id"])
    return _format_work_item(full)


async def delete_work_item(item_id: int, tool_context) -> dict:
    """Delete a work item from Azure DevOps (moves it to the recycle bin).

    Args:
        item_id: The numeric work item ID to delete.

    Returns confirmation of the deletion.
    """
    client = _get_ado_client(tool_context)
    # Fetch title before deleting for confirmation message
    raw = await client.get_work_item(item_id)
    title = raw.get("fields", {}).get("System.Title", "")
    await client.delete_work_item(item_id)
    return {"id": item_id, "title": title, "deleted": True}


async def list_work_items(query: str, tool_context) -> dict:
    """Run a WIQL query against Azure DevOps to find work items.

    Args:
        query: A WIQL query string. Example:
            "SELECT [System.Id] FROM workitems WHERE [System.WorkItemType] = 'Epic' AND [System.State] <> 'Removed' ORDER BY [System.CreatedDate] DESC"

    Returns a list of matching work item references with id and url.
    Use get_work_item to fetch full details for individual items.
    """
    client = _get_ado_client(tool_context)
    result = await client.query_work_items(query)
    items = result.get("workItems", [])
    return {
        "work_items": [{"id": wi["id"], "url": wi.get("url", "")} for wi in items],
        "count": len(items),
    }
