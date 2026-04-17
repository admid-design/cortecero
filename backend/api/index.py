"""
Vercel ASGI entrypoint para CorteCero API.
Vercel Python runtime soporta ASGI directamente — exportamos `app`.
"""
import sys
import os

# Añade backend/ al path para que `app.*` resuelva correctamente.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: F401 — Vercel busca `app` en este módulo
