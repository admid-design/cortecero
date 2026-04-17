"""
ETA Calculator — Bloque B2 (ETA-001)

Calcula la hora estimada de llegada a una parada a partir de:
  - Posición actual del conductor (lat, lng)
  - Posición de destino (lat, lng)
  - Velocidad media configurable (default: 40 km/h en reparto urbano)

Fórmula: Haversine para distancia + tiempo = distancia / velocidad.
No usa tráfico en tiempo real (eso requiere Google Distance Matrix API — fase posterior).

Esta estimación es suficiente para detectar retrasos significativos (>15 min)
y alertar al dispatcher. Para ETAs precisas, el optimize de Google ya hace
el trabajo en el momento de la planificación.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

# Radio de la Tierra en km
_EARTH_RADIUS_KM = 6371.0

# Velocidad media de reparto en área urbana/interurbana Mallorca
DEFAULT_SPEED_KMH = 40.0

# Margen mínimo de servicio en parada (para no llegar a ETA=ahora mismo)
MIN_SERVICE_GAP_SECONDS = 60


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Distancia en km entre dos coordenadas usando la fórmula Haversine.
    Precisa para distancias cortas (<500 km) — suficiente para reparto local.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


def calculate_eta(
    current_lat: float,
    current_lng: float,
    stop_lat: float,
    stop_lng: float,
    average_speed_kmh: float = DEFAULT_SPEED_KMH,
    reference_time: datetime | None = None,
) -> datetime:
    """
    Calcula la ETA estimada de llegada al destino.

    Args:
        current_lat/lng: posición actual del conductor
        stop_lat/lng: posición del destino
        average_speed_kmh: velocidad media en km/h (default 40)
        reference_time: momento de cálculo (default: ahora en UTC)

    Returns:
        datetime con timezone UTC de la llegada estimada.
        Mínimo: reference_time + MIN_SERVICE_GAP_SECONDS.
    """
    if average_speed_kmh <= 0:
        raise ValueError(f"average_speed_kmh debe ser > 0, recibido: {average_speed_kmh}")

    now = reference_time or datetime.now(UTC)
    distance_km = haversine_km(current_lat, current_lng, stop_lat, stop_lng)
    travel_seconds = (distance_km / average_speed_kmh) * 3600
    travel_seconds = max(travel_seconds, MIN_SERVICE_GAP_SECONDS)
    return now + timedelta(seconds=travel_seconds)


def delay_minutes(original_eta: datetime, recalculated_eta: datetime) -> float:
    """
    Retorna los minutos de retraso entre la ETA original y la recalculada.
    Positivo = retraso. Negativo = adelanto.
    """
    delta = recalculated_eta - original_eta
    return delta.total_seconds() / 60
