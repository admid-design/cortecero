#!/usr/bin/env python3
"""
GOOGLE-SMOKE-001 — Smoke test: Route Optimization real (Google API)

Valida el proveedor GoogleRouteOptimizationProvider end-to-end contra
el proyecto 'samurai-system' sin modificar código ni repo.

Variables de entorno requeridas:
  CORTECERO_BASE_URL       URL del backend (default: http://localhost:8000)
  CORTECERO_TENANT_SLUG    Slug del tenant a usar (default: demo-cortecero)
  CORTECERO_EMAIL          Usuario logistics/admin (default: logistics@demo.cortecero.app)
  CORTECERO_PASSWORD       Contraseña (default: logistics123)

  Para ejecutar optimize sobre una ruta existente:
    CORTECERO_ROUTE_ID     UUID de una ruta en estado 'draft' con paradas

  Para descubrir rutas disponibles sin ejecutar optimize:
    SMOKE_LIST_ROUTES=1

  Para crear y optimizar una ruta nueva con las primeras N órdenes plannificadas:
    SMOKE_CREATE_ROUTE=1
    SMOKE_ORDER_LIMIT=5      (default: 5, máx recomendado: 10)

Uso típico:
  export GOOGLE_APPLICATION_CREDENTIALS=/ruta/privada/service-account.json
  export GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system
  export CORTECERO_ROUTE_ID=<uuid>
  python smoke_google_optimization.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

try:
    import requests
except ImportError:
    print("ERROR: 'requests' no instalado. Ejecuta: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config desde entorno
# ---------------------------------------------------------------------------
BASE_URL       = os.getenv("CORTECERO_BASE_URL", "http://localhost:8000").rstrip("/")
TENANT_SLUG    = os.getenv("CORTECERO_TENANT_SLUG", "demo-cortecero")
EMAIL          = os.getenv("CORTECERO_EMAIL", "logistics@demo.cortecero.app")
PASSWORD       = os.getenv("CORTECERO_PASSWORD", "logistics123")
ROUTE_ID       = os.getenv("CORTECERO_ROUTE_ID", "")
LIST_ROUTES    = os.getenv("SMOKE_LIST_ROUTES", "").strip() in ("1", "true", "yes")
CREATE_ROUTE   = os.getenv("SMOKE_CREATE_ROUTE", "").strip() in ("1", "true", "yes")
ORDER_LIMIT    = int(os.getenv("SMOKE_ORDER_LIMIT", "5"))
MIN_STOPS      = int(os.getenv("SMOKE_MIN_STOPS", "2"))
PREFERRED_STOPS = int(os.getenv("SMOKE_PREFERRED_STOPS", "3"))

DIV  = "=" * 72
DIV2 = "-" * 72

def ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def bail(msg: str) -> None:
    print(f"\n[FATAL] {msg}")
    sys.exit(1)

def pp(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def login(session: requests.Session) -> str:
    print(f"\n[AUTH] POST {BASE_URL}/auth/login")
    r = session.post(f"{BASE_URL}/auth/login", json={
        "tenant_slug": TENANT_SLUG,
        "email": EMAIL,
        "password": PASSWORD,
    }, timeout=15)
    if r.status_code != 200:
        bail(f"Login fallido ({r.status_code}): {r.text}")
    token = r.json()["access_token"]
    print(f"[AUTH] OK — token obtenido para {EMAIL} @ {TENANT_SLUG}")
    return token

# ---------------------------------------------------------------------------
# Descubrir rutas draft disponibles
# ---------------------------------------------------------------------------
def list_draft_routes(session: requests.Session, token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{BASE_URL}/routes?status=draft", headers=headers, timeout=15)
    if r.status_code != 200:
        bail(f"GET /routes?status=draft falló ({r.status_code}): {r.text}")
    items = r.json().get("items", [])
    draft = [i for i in items if i.get("status") == "draft"]
    return draft

def get_route(session: requests.Session, token: str, route_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{BASE_URL}/routes/{route_id}", headers=headers, timeout=15)
    if r.status_code == 404:
        bail(f"Ruta {route_id} no encontrada")
    if r.status_code != 200:
        bail(f"GET /routes/{route_id} falló ({r.status_code}): {r.text}")
    return r.json()


def list_ready_to_dispatch_orders(session: requests.Session, token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{BASE_URL}/orders/ready-to-dispatch", headers=headers, timeout=20)
    if r.status_code != 200:
        bail(f"GET /orders/ready-to-dispatch falló ({r.status_code}): {r.text}")
    return r.json().get("items", [])


def list_customers_geo_map(session: requests.Session, token: str) -> dict[str, bool]:
    headers = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{BASE_URL}/admin/customers", params={"active": "true"}, headers=headers, timeout=20)
    if r.status_code != 200:
        bail(f"GET /admin/customers falló ({r.status_code}): {r.text}")
    items = r.json().get("items", [])
    geo_map: dict[str, bool] = {}
    for row in items:
        customer_id = str(row.get("id"))
        has_geo = row.get("lat") is not None and row.get("lng") is not None
        geo_map[customer_id] = has_geo
    return geo_map


def _resolve_best_group_with_geo(
    orders: list[dict],
    customer_geo_map: dict[str, bool],
) -> tuple[tuple[str, str], list[dict]] | None:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    skipped_missing_geo = 0

    for order in orders:
        customer_id = str(order.get("customer_id"))
        if not customer_geo_map.get(customer_id, False):
            skipped_missing_geo += 1
            continue
        key = (str(order["service_date"]), str(order["zone_id"]))
        grouped[key].append(order)

    if not grouped:
        print(
            "[SETUP] No hay pedidos 'ready-to-dispatch' con geocoordenadas completas "
            f"(descartados por MISSING_GEO: {skipped_missing_geo})."
        )
        return None

    print("\n[SETUP] Grupos aptos por (service_date, zone_id) con geo completo:")
    group_sizes = Counter({key: len(rows) for key, rows in grouped.items()})
    for (svc_date, zone_id), count in group_sizes.most_common():
        print(f"  - {svc_date} | {zone_id} -> {count} órdenes")

    min_required = max(2, MIN_STOPS)
    preferred = max(min_required, PREFERRED_STOPS)

    preferred_groups = [
        (key, rows) for key, rows in grouped.items() if len(rows) >= preferred
    ]
    if preferred_groups:
        best_key, best_rows = max(preferred_groups, key=lambda item: len(item[1]))
        return best_key, best_rows

    min_groups = [
        (key, rows) for key, rows in grouped.items() if len(rows) >= min_required
    ]
    if min_groups:
        best_key, best_rows = max(min_groups, key=lambda item: len(item[1]))
        return best_key, best_rows

    print(
        "[SETUP] Ningún grupo alcanza el mínimo de paradas para smoke real: "
        f"min_required={min_required}, preferred={preferred}."
    )
    return None

# ---------------------------------------------------------------------------
# Crear ruta draft desde órdenes ready-to-dispatch (modo SMOKE_CREATE_ROUTE)
# ---------------------------------------------------------------------------
def create_draft_route(session: requests.Session, token: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\n[SETUP] Buscando órdenes ready-to-dispatch...")
    orders = list_ready_to_dispatch_orders(session, token)
    if not orders:
        bail("No hay órdenes en estado 'planned'. El tenant necesita datos de prueba.")
    print(f"[SETUP] {len(orders)} órdenes disponibles en ready-to-dispatch.")

    customer_geo_map = list_customers_geo_map(session, token)
    best_group = _resolve_best_group_with_geo(orders, customer_geo_map)
    if not best_group:
        bail(
            "No hay dataset apto para smoke real.\n"
            "Criterio actual: órdenes ready-to-dispatch con customer.lat/lng y "
            f"grupo (service_date+zone_id) con al menos {max(2, MIN_STOPS)} paradas."
        )
    group_key, group_orders = best_group
    svc_date, zone_id = group_key
    min_required = max(2, MIN_STOPS)
    limit_effective = max(min_required, ORDER_LIMIT)
    selected = group_orders[:limit_effective]
    order_ids = [o["id"] for o in selected]
    print(
        f"[SETUP] Grupo seleccionado: service_date={svc_date} zone_id={zone_id} | "
        f"{len(group_orders)} candidatas geo-ok -> usando {len(order_ids)}"
    )

    print(f"[SETUP] Buscando vehículos disponibles...")
    r = session.get(f"{BASE_URL}/vehicles/available", headers=headers, timeout=15)
    if r.status_code != 200:
        bail(f"GET /vehicles/available falló ({r.status_code}): {r.text}")
    vehicles = r.json().get("items", [])
    if not vehicles:
        bail("No hay vehículos disponibles.")
    vehicle = vehicles[0]
    print(f"[SETUP] Vehículo seleccionado: {vehicle['code']} ({vehicle['id']})")

    print(f"[SETUP] Buscando plan locked para service_date={svc_date} zone_id={zone_id}...")
    r = session.get(
        f"{BASE_URL}/plans",
        params={"service_date": svc_date, "zone_id": zone_id, "status": "locked"},
        headers=headers, timeout=15,
    )
    if r.status_code != 200:
        bail(f"GET /plans falló ({r.status_code}): {r.text}")
    plans = r.json().get("items", [])
    if not plans:
        bail(
            f"No hay plan en estado 'locked' para service_date={svc_date} zone_id={zone_id}. "
            "El tenant necesita un plan bloqueado para esa zona/fecha. "
            "Alternativamente usa CORTECERO_ROUTE_ID con una ruta draft existente."
        )
    plan_id = plans[0]["id"]
    print(f"[SETUP] Plan resuelto: {plan_id}")

    payload = {
        "plan_id": plan_id,
        "service_date": svc_date,
        "routes": [
            {
                "vehicle_id": vehicle["id"],
                "driver_id": vehicle.get("driver", {}).get("id"),
                "order_ids": order_ids,
            }
        ],
    }
    print(f"[SETUP] POST /routes/plan con {len(order_ids)} paradas...")
    r = session.post(f"{BASE_URL}/routes/plan", json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 201):
        bail(f"POST /routes/plan falló ({r.status_code}): {r.text}")
    body = r.json()
    created = body.get("routes_created", body.get("routes", body.get("items", [])))
    if not created:
        bail(f"POST /routes/plan no devolvió rutas: {body}")
    route_id = created[0]["id"]
    print(f"[SETUP] Ruta creada: {route_id}")
    return route_id

# ---------------------------------------------------------------------------
# Ejecutar optimize y capturar evidencia
# ---------------------------------------------------------------------------
def run_optimize(session: requests.Session, token: str, route_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/routes/{route_id}/optimize"
    print(f"\n[OPTIMIZE] POST {url}")
    t0 = time.monotonic()
    r = session.post(url, json={}, headers=headers, timeout=120)
    elapsed = time.monotonic() - t0
    return {"status_code": r.status_code, "elapsed_s": round(elapsed, 3), "body": r.json() if r.text else {}, "raw": r.text}

# ---------------------------------------------------------------------------
# Verificaciones
# ---------------------------------------------------------------------------
def verify(route_before: dict, result: dict) -> list[str]:
    failures = []
    body = result["body"]

    if result["status_code"] != 200:
        failures.append(f"HTTP {result['status_code']} (esperado 200)")
        return failures

    if body.get("status") != "planned":
        failures.append(f"status={body.get('status')!r} (esperado 'planned')")

    if not body.get("optimization_request_id"):
        failures.append("optimization_request_id vacío o ausente")

    resp_json = body.get("optimization_response_json")
    if not resp_json:
        failures.append("optimization_response_json vacío o ausente")
    elif resp_json.get("provider") != "google":
        failures.append(f"provider={resp_json.get('provider')!r} (esperado 'google')")

    stops = body.get("stops", [])
    if not stops:
        failures.append("No hay stops en la respuesta")
    else:
        missing_eta = [s["id"] for s in stops if not s.get("estimated_arrival_at")]
        if missing_eta:
            failures.append(f"estimated_arrival_at ausente en stops: {missing_eta}")

    return failures

# ---------------------------------------------------------------------------
# Informe final
# ---------------------------------------------------------------------------
def print_report(
    route_id: str,
    route_before: dict,
    result: dict,
    failures: list[str],
) -> None:
    body = result["body"]
    resp_json = body.get("optimization_response_json", {}) if result["status_code"] == 200 else {}

    print(f"\n{DIV}")
    print("GOOGLE-SMOKE-001 — INFORME DE EVIDENCIA")
    print(f"Generado: {ts()}")
    print(DIV)

    print(f"\nTicket:          GOOGLE-SMOKE-001")
    print(f"Entorno:         {BASE_URL}")
    print(f"Tenant:          {TENANT_SLUG}")
    print(f"Proyecto Google: {os.getenv('GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID', '(no seteado)')}")
    print(f"ADC:             {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'ADC implícito / gcloud')}")

    print(f"\n{DIV2}")
    print("RUTA/PLAN PROBADO")
    print(DIV2)
    stops_before = route_before.get("stops", [])
    print(f"Route ID:        {route_id}")
    print(f"Status antes:    {route_before.get('status')}")
    print(f"Vehículo:        {route_before.get('vehicle_id')}")
    print(f"Paradas antes:   {len(stops_before)}")
    print(f"Status HTTP:     {result['status_code']}")
    print(f"Tiempo elapsed:  {result['elapsed_s']}s")

    print(f"\n{DIV2}")
    print("RESULTADO DEL OPTIMIZE REAL")
    print(DIV2)
    if result["status_code"] == 200:
        stops_after = body.get("stops", [])
        print(f"Status después:             {body.get('status')}")
        print(f"optimization_request_id:    {body.get('optimization_request_id')}")
        print(f"provider (response_json):   {resp_json.get('provider')}")
        print(f"Paradas optimizadas:        {len(stops_after)}")
        if stops_after:
            seqs_before = sorted(s.get("sequence_number", 0) for s in stops_before)
            seqs_after  = sorted(s.get("sequence_number", 0) for s in stops_after)
            print(f"Secuencias antes:           {seqs_before}")
            print(f"Secuencias después:         {seqs_after}")
            print(f"\nParadas con ETA:")
            for s in sorted(stops_after, key=lambda x: x.get("sequence_number", 0)):
                print(f"  seq={s.get('sequence_number'):>2}  order={s.get('order_id')}  eta={s.get('estimated_arrival_at')}")
    else:
        print(f"Error: {result['raw'][:500]}")

    print(f"\n{DIV2}")
    print("EVIDENCIA — optimization_response_json (resumen)")
    print(DIV2)
    if resp_json:
        routes_raw = resp_json.get("routes", [])
        print(f"routes count:       {len(routes_raw)}")
        if routes_raw:
            r0 = routes_raw[0]
            visits = r0.get("visits", [])
            print(f"visits count:       {len(visits)}")
            metrics = r0.get("routeDistanceMeters") or r0.get("metrics", {})
            print(f"routeDistanceMeters: {r0.get('routeDistanceMeters', 'n/a')}")
            print(f"totalDuration:       {(r0.get('metrics') or {}).get('totalDuration', 'n/a')}")
        print(f"\nkeys top-level:     {list(resp_json.keys())}")
    else:
        print("(sin datos — optimize falló o provider=mock)")

    print(f"\n{DIV2}")
    print("VERIFICACIONES")
    print(DIV2)
    if not failures:
        print("✓ Todas las verificaciones pasaron")
    else:
        for f in failures:
            print(f"✗ {f}")

    print(f"\n{DIV}")
    verdict = "GO ✓" if not failures else "NO-GO ✗"
    print(f"ESTADO FINAL: {verdict}")
    print(DIV)

    if not failures:
        sys.exit(0)
    else:
        sys.exit(1)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(DIV)
    print("GOOGLE-SMOKE-001 — Route Optimization Smoke Test")
    print(f"Base URL: {BASE_URL} | Tenant: {TENANT_SLUG}")
    print(DIV)

    # Validación mínima de entorno
    project_id = os.getenv("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID", "")
    if not project_id:
        bail(
            "GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID no está seteado.\n"
            "El backend usará el MockProvider en lugar de Google real.\n"
            "Setea la variable y asegura que GOOGLE_APPLICATION_CREDENTIALS apunta al SA."
        )

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    token = login(session)

    # -----------------------------------------------------------------------
    # Modo: listar rutas draft disponibles
    # -----------------------------------------------------------------------
    if LIST_ROUTES:
        print(f"\n[LIST] Rutas en estado draft:")
        drafts = list_draft_routes(session, token)
        if not drafts:
            print("  (ninguna — crea una desde el dispatcher o usa SMOKE_CREATE_ROUTE=1)")
        for d in drafts:
            stops_count = len(d.get("stops", []))
            print(f"  {d['id']}  date={d.get('service_date')}  stops={stops_count}  vehicle={d.get('vehicle_id')}")
        print(f"\nPara ejecutar el smoke test:")
        print(f"  export CORTECERO_ROUTE_ID=<uuid>")
        print(f"  python {os.path.basename(__file__)}")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Modo: crear ruta draft automáticamente
    # -----------------------------------------------------------------------
    route_id = ROUTE_ID.strip()
    if not route_id and CREATE_ROUTE:
        route_id = create_draft_route(session, token)

    if not route_id:
        bail(
            "Especifica una ruta:\n"
            "  CORTECERO_ROUTE_ID=<uuid>  — optimizar ruta existente\n"
            "  SMOKE_LIST_ROUTES=1        — listar rutas draft disponibles\n"
            "  SMOKE_CREATE_ROUTE=1       — crear ruta automáticamente desde órdenes planned"
        )

    # -----------------------------------------------------------------------
    # Capturar estado ANTES del optimize
    # -----------------------------------------------------------------------
    print(f"\n[PRE]  Capturando estado de ruta {route_id}...")
    route_before = get_route(session, token, route_id)
    if route_before.get("status") != "draft":
        bail(
            f"La ruta {route_id} está en estado '{route_before.get('status')}', "
            f"no en 'draft'. El optimize solo funciona sobre rutas draft."
        )
    stops_before = route_before.get("stops", [])
    if not stops_before:
        bail(
            f"La ruta {route_id} no tiene paradas. "
            f"Usa POST /routes/plan para añadir paradas antes de optimizar, "
            f"o usa SMOKE_CREATE_ROUTE=1 para que el script las cree."
        )
    print(f"[PRE]  OK — {len(stops_before)} paradas, status=draft")

    # -----------------------------------------------------------------------
    # Ejecutar optimize
    # -----------------------------------------------------------------------
    result = run_optimize(session, token, route_id)

    # -----------------------------------------------------------------------
    # Verificar y reportar
    # -----------------------------------------------------------------------
    failures = verify(route_before, result)
    print_report(route_id, route_before, result, failures)


if __name__ == "__main__":
    main()
