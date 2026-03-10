"""Common helpers for automatic access rights synchronization.

Principle: if a dashboard has roles=[R1, R2], then each role R1, R2
automatically receives datasource_access to ALL datasets of that dashboard.
This guarantees: add a user to a group -> they can see the dashboard and its data.
"""

from typing import Any


async def find_datasource_permissions(
    client: Any,
    dataset_ids: set[int],
) -> dict[int, int]:
    """Find permission_view_menu_id for datasource_access on the specified datasets.

    Args:
        client: SupersetClient instance.
        dataset_ids: Set of dataset IDs to look up.

    Returns:
        Mapping of {dataset_id: permission_view_menu_id}.
    """
    found: dict[int, int] = {}
    page = 0
    while page < 50:
        try:
            resp = await client.get(
                "/api/v1/security/permissions-resources/",
                params={"q": f"(page:{page},page_size:100)"},
            )
        except Exception:
            break
        items = resp.get("result", [])
        if not items:
            break
        for item in items:
            perm_name = item.get("permission", {}).get("name", "")
            view_name = item.get("view_menu", {}).get("name", "")
            if perm_name == "datasource_access":
                for ds_id in dataset_ids:
                    if f"(id:{ds_id})" in view_name:
                        found[ds_id] = item["id"]
        if found.keys() >= dataset_ids:
            break
        if len(items) < 100:
            break
        page += 1
    return found


async def auto_sync_dashboard_access(
    client: Any,
    dashboard_id: int,
) -> dict[str, Any]:
    """Automatically synchronize datasource_access for dashboard roles.

    For each role assigned to the dashboard:
    1. Retrieves all dashboard datasets
    2. Finds datasource_access permission_view_menu_id for each
    3. Checks current role permissions
    4. Adds any missing permissions

    Args:
        client: SupersetClient instance.
        dashboard_id: ID of the dashboard.

    Returns:
        Synchronization report dict.
    """
    result = {
        "dashboard_id": dashboard_id,
        "synced_roles": [],
        "already_ok": [],
        "errors": [],
    }

    # Fetch the dashboard
    try:
        db_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        db_data = db_resp.get("result", {})
    except Exception as e:
        result["errors"].append(f"Failed to fetch dashboard {dashboard_id}: {e}")
        return result

    # Dashboard roles
    db_roles = db_data.get("roles", [])
    if not db_roles:
        result["already_ok"].append("No roles on dashboard — sync not required")
        return result

    role_ids = [r["id"] for r in db_roles if isinstance(r, dict)]

    # Dashboard datasets
    try:
        ds_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}/datasets")
        datasets = ds_resp.get("result", [])
    except Exception as e:
        result["errors"].append(f"Failed to fetch datasets: {e}")
        return result

    if not datasets:
        result["already_ok"].append("No datasets — nothing to sync")
        return result

    dataset_ids = {d["id"] for d in datasets if isinstance(d, dict)}
    dataset_names = {d["id"]: d.get("table_name", f"id:{d['id']}") for d in datasets}

    # Find permission_view_menu_id for each dataset
    ds_perms = await find_datasource_permissions(client, dataset_ids)

    if not ds_perms:
        result["errors"].append(
            f"No datasource_access permissions found for datasets: "
            f"{[dataset_names.get(did, did) for did in dataset_ids]}"
        )
        return result

    # For each role, check and add missing permissions
    for role_id in role_ids:
        try:
            perms_resp = await client.get(f"/api/v1/security/roles/{role_id}/permissions/")
            current_perm_ids = set()
            for p in perms_resp.get("result", []):
                if isinstance(p, dict) and "id" in p:
                    current_perm_ids.add(p["id"])
                elif isinstance(p, int):
                    current_perm_ids.add(p)

            # Check which datasource_access permissions are missing
            missing = {}
            for ds_id, pvm_id in ds_perms.items():
                if pvm_id not in current_perm_ids:
                    missing[ds_id] = pvm_id

            if not missing:
                result["already_ok"].append(f"Role {role_id}: all datasource_access already present")
                continue

            # Add missing permissions
            new_perm_ids = sorted(current_perm_ids | set(missing.values()))
            await client.put(
                f"/api/v1/security/roles/{role_id}/permissions/",
                json_data={"permission_view_menu_ids": new_perm_ids},
            )

            missing_names = [dataset_names.get(did, f"id:{did}") for did in missing]
            result["synced_roles"].append(
                {
                    "role_id": role_id,
                    "added_datasets": missing_names,
                    "total_permissions": len(new_perm_ids),
                }
            )

        except Exception as e:
            result["errors"].append(f"Error for role {role_id}: {e}")

    return result


async def auto_sync_chart_dashboards(
    client: Any,
    chart_id: int | None = None,
    datasource_id: int | None = None,
) -> list[dict[str, Any]]:
    """Synchronize access for all dashboards containing the specified chart.

    Called after chart_create/chart_update. Finds dashboards that include the chart
    and runs auto_sync_dashboard_access for each.

    Args:
        client: SupersetClient instance.
        chart_id: ID of the chart (if known).
        datasource_id: ID of the chart's dataset (optional, for optimization).

    Returns:
        List of sync reports, one per synchronized dashboard.
    """
    results = []

    if not chart_id:
        return results

    # Fetch the chart and its dashboards
    try:
        chart_resp = await client.get(f"/api/v1/chart/{chart_id}")
        chart_data = chart_resp.get("result", {})
        dashboards = chart_data.get("dashboards", [])
    except Exception:
        return results

    for db in dashboards:
        db_id = db.get("id") if isinstance(db, dict) else db
        if db_id:
            sync_result = await auto_sync_dashboard_access(client, db_id)
            results.append(sync_result)

    return results
