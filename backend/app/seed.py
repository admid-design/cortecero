import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import SessionLocal
from app.domain import build_effective_cutoff_at, compute_lateness, initial_order_status
from app.models import (
    Customer,
    EntityType,
    ExceptionItem,
    ExceptionStatus,
    ExceptionType,
    Order,
    OrderStatus,
    OrderLine,
    Plan,
    PlanOrder,
    PlanStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Zone,
    InclusionType,
    AuditLog,
    Vehicle,
    Driver,
    Route,
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    Incident,
    IncidentType,
    IncidentSeverity,
    IncidentStatus,
    RouteEvent,
    RouteEventType,
    RouteEventActorType,
)
from app.security import hash_password


def now_utc() -> datetime:
    return datetime.now(UTC)


def seed() -> None:
    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="CorteCero Demo",
                slug="demo-cortecero",
                default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
                default_timezone="Europe/Madrid",
                auto_lock_enabled=False,
                created_at=now_utc(),
            )
            db.add(tenant)
            db.flush()

        users_by_role = {}
        for role, email in [
            (UserRole.office, "office@demo.cortecero.app"),
            (UserRole.logistics, "logistics@demo.cortecero.app"),
            (UserRole.admin, "admin@demo.cortecero.app"),
        ]:
            user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    email=email,
                    full_name=role.value.title(),
                    password_hash=hash_password(f"{role.value}123"),
                    role=role,
                    is_active=True,
                    created_at=now_utc(),
                )
                db.add(user)
                db.flush()
            users_by_role[role.value] = user

        zone_a = db.scalar(select(Zone).where(Zone.tenant_id == tenant.id, Zone.name == "Centro"))
        if not zone_a:
            zone_a = Zone(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Centro",
                default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
                timezone="Europe/Madrid",
                active=True,
                created_at=now_utc(),
            )
            db.add(zone_a)
            db.flush()

        zone_b = db.scalar(select(Zone).where(Zone.tenant_id == tenant.id, Zone.name == "Costa"))
        if not zone_b:
            zone_b = Zone(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Costa",
                default_cutoff_time=datetime.strptime("09:30", "%H:%M").time(),
                timezone="Europe/Madrid",
                active=True,
                created_at=now_utc(),
            )
            db.add(zone_b)
            db.flush()

        # Coordenadas reales de puntos de entrega en Mallorca (Bloque G).
        # Centro = Palma centro urbano; Costa = costa norte/este.
        # Fuente: Google Maps, puntos representativos de polígonos y comercios.
        _customer_geo = [
            # Centro (zone_a) — Palma
            ("Cliente 01", 39.5696,  2.6502, "Passeig del Born 12, Palma"),
            ("Cliente 02", 39.5753,  2.6541, "Plaça d'Espanya 5, Palma"),
            ("Cliente 03", 39.5820,  2.6618, "Polígon Son Castelló, Palma"),
            ("Cliente 04", 39.6172,  2.6496, "Camí Vell de Bunyola 39, Palma"),
            ("Cliente 05", 39.5564,  2.6267, "C/ Arxiduc Lluís Salvador 8, Palma"),
            # Costa (zone_b) — norte
            ("Cliente 06", 39.8531,  3.1207, "Plaça Constitució 3, Alcúdia"),
            ("Cliente 07", 39.7590,  3.1543, "Av. Diagonal, Can Picafort"),
            ("Cliente 08", 39.7089,  3.4593, "C/ Leonor Servera 42, Cala Ratjada"),
            ("Cliente 09", 39.7989,  3.1210, "C/ Marjals 7, Playa de Muro"),
            ("Cliente 10", 39.9121,  3.0762, "Passeig Anglada Camarassa, Pto Pollensa"),
        ]

        customers = []
        for idx in range(10):
            zone = zone_a if idx < 5 else zone_b
            name = f"Cliente {idx + 1:02d}"
            _, lat_val, lng_val, addr = _customer_geo[idx]
            customer = db.scalar(select(Customer).where(Customer.tenant_id == tenant.id, Customer.name == name))
            if not customer:
                customer = Customer(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    zone_id=zone.id,
                    name=name,
                    priority=0,
                    cutoff_override_time=None,
                    lat=lat_val,
                    lng=lng_val,
                    delivery_address=addr,
                    active=True,
                    created_at=now_utc(),
                )
                db.add(customer)
                db.flush()
            customers.append(customer)

        service_date = (datetime.now(ZoneInfo("Europe/Madrid")) + timedelta(days=1)).date()

        existing_orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date)))
        if len(existing_orders) < 20:
            for idx in range(20):
                customer = customers[idx % len(customers)]
                zone = zone_a if customer.zone_id == zone_a.id else zone_b
                external_ref = f"DEMO-{service_date.strftime('%Y%m%d')}-{idx + 1:03d}"

                present = db.scalar(
                    select(Order).where(
                        Order.tenant_id == tenant.id,
                        Order.external_ref == external_ref,
                        Order.service_date == service_date,
                    )
                )
                if present:
                    continue

                cutoff_time = customer.cutoff_override_time or zone.default_cutoff_time or tenant.default_cutoff_time
                effective_cutoff = build_effective_cutoff_at(service_date, cutoff_time, zone.timezone)
                created_at = effective_cutoff - timedelta(hours=2) if idx < 12 else effective_cutoff + timedelta(hours=1)
                is_late, reason = compute_lateness(created_at, effective_cutoff)

                order = Order(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    customer_id=customer.id,
                    zone_id=zone.id,
                    external_ref=external_ref,
                    requested_date=service_date,
                    service_date=service_date,
                    created_at=created_at,
                    status=initial_order_status(is_late),
                    is_late=is_late,
                    lateness_reason=reason,
                    effective_cutoff_at=effective_cutoff,
                    source_channel=SourceChannel.office,
                    ingested_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(order)
                db.flush()

                db.add(
                    OrderLine(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        order_id=order.id,
                        sku=f"SKU-{idx + 1:03d}",
                        qty=1,
                        weight_kg=2.5,
                        volume_m3=0.02,
                        created_at=now_utc(),
                    )
                )

        open_plan = db.scalar(
            select(Plan).where(
                Plan.tenant_id == tenant.id,
                Plan.service_date == service_date,
                Plan.zone_id == zone_a.id,
            )
        )
        if not open_plan:
            open_plan = Plan(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                service_date=service_date,
                zone_id=zone_a.id,
                status=PlanStatus.open,
                version=1,
                locked_at=None,
                locked_by=None,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(open_plan)
            db.flush()

        locked_plan = db.scalar(
            select(Plan).where(
                Plan.tenant_id == tenant.id,
                Plan.service_date == service_date,
                Plan.zone_id == zone_b.id,
            )
        )
        if not locked_plan:
            locked_plan = Plan(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                service_date=service_date,
                zone_id=zone_b.id,
                status=PlanStatus.locked,
                version=2,
                locked_at=now_utc(),
                locked_by=users_by_role["logistics"].id,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(locked_plan)
            db.flush()

        all_orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date)))
        by_external = {o.external_ref: o for o in all_orders}

        planned_candidate = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-001")
        if planned_candidate:
            exists_plan_order = db.scalar(
                select(PlanOrder).where(PlanOrder.tenant_id == tenant.id, PlanOrder.order_id == planned_candidate.id)
            )
            if not exists_plan_order:
                db.add(
                    PlanOrder(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        plan_id=open_plan.id,
                        order_id=planned_candidate.id,
                        inclusion_type=InclusionType.normal,
                        added_at=now_utc(),
                        added_by=users_by_role["logistics"].id,
                    )
                )
                planned_candidate.status = OrderStatus.planned

        pending_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-019")
        approved_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-020")
        rejected_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-018")

        for order_obj, status in [
            (pending_order, ExceptionStatus.pending),
            (approved_order, ExceptionStatus.approved),
            (rejected_order, ExceptionStatus.rejected),
        ]:
            if not order_obj:
                continue
            has_exception = db.scalar(select(ExceptionItem).where(ExceptionItem.tenant_id == tenant.id, ExceptionItem.order_id == order_obj.id))
            if has_exception:
                continue

            resolved_by = None if status == ExceptionStatus.pending else users_by_role["logistics"].id
            resolved_at = None if status == ExceptionStatus.pending else now_utc()

            db.add(
                ExceptionItem(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    order_id=order_obj.id,
                    type=ExceptionType.late_order,
                    status=status,
                    requested_by=users_by_role["office"].id,
                    resolved_by=resolved_by,
                    resolved_at=resolved_at,
                    note=f"Seed {status.value}",
                    created_at=now_utc(),
                )
            )

            if status == ExceptionStatus.rejected:
                order_obj.status = OrderStatus.exception_rejected

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                entity_type=EntityType.plan,
                entity_id=open_plan.id,
                action="seed.generated",
                actor_id=users_by_role["admin"].id,
                ts=now_utc(),
                request_id="seed",
                metadata_json={"service_date": str(service_date)},
            )
        )

        # ========================================================================
        # ROUTING POC SEED DATA — Flota real Kelko Mallorca
        # Fuente: Kelko - Flota Vehiculos.xlsx + Scan_fichatec.vehiculs.pdf
        # Turno: 07:00–15:00 | Almacén: 39.6578°N, 2.7384°E (Binissalem)
        # ========================================================================

        # ------------------------------------------------------------------
        # Vehículos reales Kelko
        # code = matrícula | name = descripción operativa
        # capacity_kg = carga útil (MTMA – tara) según ficha técnica / flota
        # Nota ZBE Palma (restricciones DGT):
        #   - 7157CMP: PROHIBIDO zona ZBE Palma (sin etiqueta ambiental)
        #   - 4093DWM: restringido desde 2027 (etiqueta C)
        # ------------------------------------------------------------------
        vehicles = {}
        for code, name, capacity in [
            # Camiones grandes (carnet C, turno completo)
            ("0866GFC", "IVECO ML140E22 14T – Tito",        7580.0),   # tara 6420, MTMA 14000
            ("0698FPH", "IVECO ML100E22 10T – Amengual",    4975.0),   # tara 5025, MTMA 10000
            ("5520MPL", "DAF 12T – Dani",                   6145.0),   # MTMA ~12000
            # Furgonetas (carnet B)
            ("7822HXS", "Furgoneta 2T – Marcelo",           1500.0),
            ("4093DWM", "Furgoneta 2T – Tomeu",             1400.0),   # ZBE restringida desde 2027
            # Vehículo reserva/incidencias
            ("7157CMP", "Camión reserva – ZBE prohibido",   3500.0),   # NO apto zona ZBE Palma
        ]:
            vehicle = db.scalar(select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.code == code))
            if not vehicle:
                vehicle = Vehicle(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    code=code,
                    name=name,
                    capacity_kg=capacity,
                    active=(code != "7157CMP"),  # reserva fuera de rotación activa
                    created_at=now_utc(),
                )
                db.add(vehicle)
                db.flush()
            vehicles[code] = vehicle

        # ------------------------------------------------------------------
        # Choferes reales Kelko
        # Fuente: hoja "Choferes" de Kelko - Flota Vehiculos.xlsx
        # phone = placeholder operativo (formato ES)
        # ADR: Tito y Amengual certificados para mercancías peligrosas
        # ------------------------------------------------------------------
        drivers = {}
        for drv_key, name, phone, vehicle_code in [
            # Carnet C (camiones)
            ("tito",      "Tito",      "600100101", "0866GFC"),
            ("amengual",  "Amengual",  "600100102", "0698FPH"),
            ("dani",      "Dani",      "600100103", "5520MPL"),
            ("juan",      "Juan",      "600100104", None),         # carnet C, sin camión fijo
            # Carnet B (furgonetas)
            ("marcelo",   "Marcelo",   "600100105", "7822HXS"),
            ("tomeu",     "Tomeu",     "600100106", "4093DWM"),
        ]:
            driver = db.scalar(select(Driver).where(Driver.tenant_id == tenant.id, Driver.phone == phone))
            if not driver:
                v_id = vehicles[vehicle_code].id if vehicle_code else None
                driver = Driver(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    vehicle_id=v_id,
                    name=name,
                    phone=phone,
                    is_active=True,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(driver)
                db.flush()
            drivers[drv_key] = driver

        # ------------------------------------------------------------------
        # Zonas operativas Kelko — calendario invierno (vigente actual)
        # Fuente: Kelko - Rutas Invierno _ Verano.xlsx
        # Invierno (nov–feb): 3 zonas/día
        # Verano  (mar–oct): 7 zonas/día
        # ------------------------------------------------------------------
        kelko_zones = {}
        for z_name, cutoff_str, tz in [
            ("Palma",                   "09:30", "Europe/Madrid"),
            ("Alcudia",                 "09:00", "Europe/Madrid"),
            ("Cala Ratjada-Cala Millor-Bares", "09:00", "Europe/Madrid"),
            # Zonas verano (inactivas en temporada baja)
            ("Can Picafort",            "09:00", "Europe/Madrid"),
            ("Playas de Muro",          "09:00", "Europe/Madrid"),
            ("Pto Alcudia",             "09:00", "Europe/Madrid"),
            ("Pto Pollensa",            "09:00", "Europe/Madrid"),
        ]:
            zone = db.scalar(select(Zone).where(Zone.tenant_id == tenant.id, Zone.name == z_name))
            if not zone:
                zone = Zone(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    name=z_name,
                    default_cutoff_time=datetime.strptime(cutoff_str, "%H:%M").time(),
                    timezone=tz,
                    active=True,
                    created_at=now_utc(),
                )
                db.add(zone)
                db.flush()
            kelko_zones[z_name] = zone

        # ------------------------------------------------------------------
        # Rutas draft para el día actual — una por zona activa (invierno)
        # Se crean solo si existe un plan locked para esa zona
        # ------------------------------------------------------------------
        routes = {}
        route_service_date = datetime.now(UTC).date()
        active_zone_driver_vehicle = [
            ("Palma",                           "tito",     "0866GFC"),
            ("Alcudia",                         "amengual", "0698FPH"),
            ("Cala Ratjada-Cala Millor-Bares",  "dani",     "5520MPL"),
        ]
        for i, (z_name, drv_key, v_code) in enumerate(active_zone_driver_vehicle):
            zone_obj = kelko_zones.get(z_name)
            if not zone_obj:
                continue
            plan = db.scalar(
                select(Plan).where(
                    Plan.tenant_id == tenant.id,
                    Plan.service_date == route_service_date,
                    Plan.zone_id == zone_obj.id,
                    Plan.status == PlanStatus.locked,
                )
            )
            if plan:
                route_key = f"RT-{route_service_date.isoformat()}-{z_name}"
                route = db.scalar(
                    select(Route).where(
                        Route.tenant_id == tenant.id,
                        Route.plan_id == plan.id,
                        Route.vehicle_id == vehicles[v_code].id,
                    )
                )
                if not route:
                    route = Route(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        plan_id=plan.id,
                        vehicle_id=vehicles[v_code].id,
                        driver_id=drivers[drv_key].id,
                        service_date=route_service_date,
                        status=RouteStatus.draft,
                        version=1,
                        optimization_request_id=None,
                        optimization_response_json=None,
                        created_at=now_utc(),
                        updated_at=now_utc(),
                        dispatched_at=None,
                        completed_at=None,
                    )
                    db.add(route)
                    db.flush()
                routes[route_key] = route

        db.commit()
        print("Seed OK")
        print("Users:")
        print(" - office@demo.cortecero.app / office123")
        print(" - logistics@demo.cortecero.app / logistics123")
        print(" - admin@demo.cortecero.app / admin123")
        print("Routing POC — Flota Kelko:")
        print(f" - {len(vehicles)} vehículos ({sum(1 for v in vehicles.values() if v.active)} activos)")
        print(f" - {len(drivers)} choferes")
        print(f" - {len(kelko_zones)} zonas operativas")
        print(f" - {len(routes)} rutas draft creadas")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
