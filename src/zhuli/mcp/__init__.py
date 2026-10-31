"""Zhuli MCP server (stdlib only).

IDE operates Zhuli: OpenCode, Trae and CodeBuddy act as MCP clients and
call this server over stdio JSON-RPC. No provider key or token is ever
returned by any tool; config output lists provider names only.
"""

__version__ = "0.2.0"
