"""Регистрация всех инструментов MCP-сервера."""

from mcp_superset.tools.audit import register_audit_tools
from mcp_superset.tools.charts import register_chart_tools
from mcp_superset.tools.dashboards import register_dashboard_tools
from mcp_superset.tools.databases import register_database_tools
from mcp_superset.tools.datasets import register_dataset_tools
from mcp_superset.tools.groups import register_group_tools
from mcp_superset.tools.queries import register_query_tools
from mcp_superset.tools.security import register_security_tools
from mcp_superset.tools.system import register_system_tools
from mcp_superset.tools.tags import register_tag_tools


def register_all_tools(mcp):
    """Регистрирует все группы инструментов в MCP-сервере."""
    register_dashboard_tools(mcp)
    register_chart_tools(mcp)
    register_database_tools(mcp)
    register_dataset_tools(mcp)
    register_query_tools(mcp)
    register_security_tools(mcp)
    register_tag_tools(mcp)
    register_system_tools(mcp)
    register_group_tools(mcp)
    register_audit_tools(mcp)
