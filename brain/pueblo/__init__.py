"""Pueblo Vivo — a local generative-agents village simulation.

The `pueblo` package is the "brain": a pure-Python cognitive engine (memory,
retrieval, reflection, planning, conversation) driven by a local LLM via Ollama,
plus a tick-based simulation loop and a FastAPI/WebSocket server that a Unity
client renders.

The cognitive core is importable and testable without Unity or the server.
"""

__version__ = "0.1.0"
