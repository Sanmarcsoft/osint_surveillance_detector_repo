import asyncio

from ghostmode.mcp_server import create_server


def test_create_server_returns_mcp_instance():
    server = create_server(port=3200)
    assert server is not None


def test_server_has_expected_tools():
    server = create_server(port=3200)
    # FastMCP 3.1.1 exposes list_tools() as an async method
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    assert "ghostmode_status" in tool_names
    assert "ghostmode_alert_test" in tool_names
    assert "ghostmode_config_validate" in tool_names
    assert "ghostmode_logs_query" in tool_names
    assert "ghostmode_alerts_list" in tool_names
    assert "ghostmode_watch_events" in tool_names
    assert "ghostmode_docs_query" in tool_names


def test_server_name():
    server = create_server(port=3200)
    assert server.name == "ghostmode"
