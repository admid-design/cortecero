"""
RouteEventBus — In-process pub/sub para eventos SSE por ruta.

Diseño: asyncio.Queue por (tenant_id, route_id).
Cuando un endpoint muta estado (arrive, complete, fail, skip, driver/location),
llama a event_bus.publish(). Los streams SSE abiertos reciben el evento.

Limitación conocida (REALTIME-001):
  asyncio.Queue no se comparte entre workers de gunicorn en modo multi-process.
  En despliegue con múltiples workers, cada proceso tiene su propia instancia
  y solo los clientes conectados al mismo worker reciben los eventos.
  Fix futuro: Redis pub/sub (bloque independiente, fuera de REALTIME-001).

Autenticación SSE (REALTIME-001):
  El endpoint /routes/{id}/stream acepta el JWT en query param ?token=<jwt>.
  Esto se acepta SOLO para smoke/local/pilot de REALTIME-001.
  SSE no soporta headers custom en browser; la solución definitiva requiere
  un diseño explícito (cookie httpOnly, ticket de corta duración, etc.).
  Esta decisión queda pendiente y NO debe considerarse contrato final.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class RouteEventBus:
    """
    Registro de queues asyncio por (tenant_id, route_id).

    Thread-safety: asyncio es single-threaded por event loop.
    No se necesita lock mientras todas las operaciones ocurran
    en el mismo loop (FastAPI con uvicorn en un worker).
    """

    def __init__(self) -> None:
        # (tenant_id_str, route_id_str) → lista de queues activas
        self._queues: dict[tuple[str, str], list[asyncio.Queue[str | None]]] = defaultdict(list)

    def publish(self, tenant_id: str, route_id: str, event_type: str, payload: dict) -> None:
        """
        Publica un evento a todos los streams SSE abiertos para (tenant_id, route_id).
        Fire-and-forget: no bloquea. Si no hay listeners, es una noop.
        """
        key = (str(tenant_id), str(route_id))
        subscribers = self._queues.get(key)
        if not subscribers:
            return

        data = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        for queue in list(subscribers):  # copia para evitar mutación durante iteración
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(
                    "RouteEventBus: queue full for route=%s, dropping event=%s",
                    route_id,
                    event_type,
                )

    async def subscribe(
        self, tenant_id: str, route_id: str
    ) -> AsyncIterator[str]:
        """
        Generador asíncrono que emite frames SSE mientras el cliente esté conectado.
        Se limpia automáticamente al cerrarse la conexión (finally).

        Yields strings con formato SSE: "event: <type>\\ndata: <json>\\n\\n"
        """
        key = (str(tenant_id), str(route_id))
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=100)
        self._queues[key].append(queue)
        logger.debug(
            "RouteEventBus: client subscribed tenant=%s route=%s (total=%d)",
            tenant_id,
            route_id,
            len(self._queues[key]),
        )
        try:
            while True:
                item = await queue.get()
                if item is None:
                    # Señal de cierre explícita (no usada en B1, disponible para futuro)
                    break
                yield item
        except asyncio.CancelledError:
            # El cliente cerró la conexión — comportamiento normal
            pass
        finally:
            subscribers = self._queues.get(key, [])
            if queue in subscribers:
                subscribers.remove(queue)
            if not subscribers and key in self._queues:
                del self._queues[key]
            logger.debug(
                "RouteEventBus: client unsubscribed tenant=%s route=%s",
                tenant_id,
                route_id,
            )

    def active_subscriber_count(self, tenant_id: str, route_id: str) -> int:
        """Para tests: número de subscriptores activos de una ruta."""
        return len(self._queues.get((str(tenant_id), str(route_id)), []))


# Singleton de proceso — importar desde aquí en routing.py y en tests
event_bus = RouteEventBus()
