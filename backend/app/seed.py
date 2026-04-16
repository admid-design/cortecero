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

        # Dataset geográfico sintético para demo/local.
        # No contiene ubicaciones ni direcciones reales de clientes.
        _customer_geo = [
            # Centro (zone_a) — Palma de Mallorca
            # Todos los clientes de zone_a están en Palma para ser alcanzables
            # desde el depot demo (39.5696, 2.6502) por carretera en la isla.
            ("Cliente 01", 39.5711, 2.6512, "Avenida Jaume III 1, Palma"),
            ("Cliente 02", 39.5752, 2.6478, "Carrer de Sant Miquel 2, Palma"),
            ("Cliente 03", 39.5688, 2.6551, "Passeig del Born 3, Palma"),
            ("Cliente 04", 39.5730, 2.6590, "Carrer de Colom 4, Palma"),
            ("Cliente 05", 39.5660, 2.6440, "Avinguda d'Argentina 5, Palma"),
            # Costa (zone_b) — Municipios costeros de Mallorca
            ("Cliente 06", 39.8517, 3.1191, "Carrer Major 6, Alcúdia"),
            ("Cliente 07", 39.7064, 3.2030, "Avinguda del Parc 7, Manacor"),
            ("Cliente 08", 39.6381, 2.9959, "Carrer de l'Arenal 8, Llucmajor"),
            ("Cliente 09", 39.7208, 2.9133, "Gran Via de Colom 9, Inca"),
            ("Cliente 10", 39.5830, 2.7920, "Carretera de Manacor 10, Algaida"),
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
            else:
                # Backfill determinista de dataset geo demo para instalaciones existentes.
                # Fuerza siempre las coordenadas canónicas del seed — sin condición de null —
                # para que instalaciones con coordenadas antiguas (e.g. Madrid) queden
                # corregidas a las coordenadas Mallorca geo-coherentes con el depot.
                needs_update = False
                if customer.zone_id != zone.id:
                    customer.zone_id = zone.id
                    needs_update = True
                if customer.lat != lat_val:
                    customer.lat = lat_val
                    needs_update = True
                if customer.lng != lng_val:
                    customer.lng = lng_val
                    needs_update = True
                if customer.delivery_address != addr:
                    customer.delivery_address = addr
                    needs_update = True
                if not customer.active:
                    customer.active = True
                    needs_update = True
                if needs_update:
                    customer.updated_at = now_utc()
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
            # Garantiza caso demo geo-ready para la referencia principal de flujo.
            # Si el pedido quedó vinculado a un cliente sin coordenadas, se corrige
            # al cliente demo 01 (geo sintético estable).
            planned_customer = db.scalar(
                select(Customer).where(
                    Customer.id == planned_candidate.customer_id,
                    Customer.tenant_id == tenant.id,
                )
            )
            if not planned_customer or planned_customer.lat is None or planned_customer.lng is None:
                planned_candidate.customer_id = customers[0].id
                planned_candidate.zone_id = customers[0].zone_id
                planned_candidate.updated_at = now_utc()

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

        # Backfill de compatibilidad para órdenes demo históricas (p.ej. DEMO-YYYYMMDD-001)
        # que ya existían antes del dataset geográfico sintético.
        legacy_demo_orders = list(
            db.scalars(
                select(Order).where(
                    Order.tenant_id == tenant.id,
                    Order.external_ref.like("DEMO-%-001"),
                )
            )
        )
        for order_obj in legacy_demo_orders:
            order_customer = db.scalar(
                select(Customer).where(
                    Customer.id == order_obj.customer_id,
                    Customer.tenant_id == tenant.id,
                )
            )
            if not order_customer or order_customer.lat is None or order_customer.lng is None:
                order_obj.customer_id = customers[0].id
                order_obj.zone_id = customers[0].zone_id
                order_obj.updated_at = now_utc()

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
        # ROUTING POC SEED DATA — Flota demo sintética
        # Dataset no identificable para desarrollo local y tests.
        # ========================================================================

        # ------------------------------------------------------------------
        # Vehículos demo
        # code = identificador interno sintético
        # capacity_kg = capacidad de carga en kg (dataset de ejemplo)
        # ------------------------------------------------------------------
        vehicles = {}
        for code, name, capacity in [
            ("VH-001", "Camion Demo A 14T", 7600.0),
            ("VH-002", "Camion Demo B 10T", 5000.0),
            ("VH-003", "Camion Demo C 12T", 6100.0),
            ("VH-004", "Furgon Demo D 2T", 1500.0),
            ("VH-005", "Furgon Demo E 2T", 1400.0),
            ("VH-006", "Vehiculo Reserva Demo", 3500.0),
        ]:
            vehicle = db.scalar(select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.code == code))
            if not vehicle:
                vehicle = Vehicle(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    code=code,
                    name=name,
                    capacity_kg=capacity,
                    active=(code != "VH-006"),  # reserva fuera de rotación activa
                    created_at=now_utc(),
                )
                db.add(vehicle)
                db.flush()
            vehicles[code] = vehicle

        # ------------------------------------------------------------------
        # Conductores demo
        # phone = identificador telefónico sintético de ejemplo
        # ------------------------------------------------------------------
        drivers = {}
        for drv_key, name, phone, vehicle_code in [
            ("driver_a", "Driver A", "700000101", "VH-001"),
            ("driver_b", "Driver B", "700000102", "VH-002"),
            ("driver_c", "Driver C", "700000103", "VH-003"),
            ("driver_d", "Driver D", "700000104", None),
            ("driver_e", "Driver E", "700000105", "VH-004"),
            ("driver_f", "Driver F", "700000106", "VH-005"),
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
        # Zonas de referencia sintéticas para ruteo demo.
        # Solo se usan si ya existen en el tenant (no se crean automáticamente).
        # ------------------------------------------------------------------
        routing_demo_zones = {}
        for z_name, cutoff_str, tz in [
            ("Centro", "10:00", "Europe/Madrid"),
            ("Costa", "09:30", "Europe/Madrid"),
            ("Periferia", "09:00", "Europe/Madrid"),
        ]:
            zone = db.scalar(select(Zone).where(Zone.tenant_id == tenant.id, Zone.name == z_name))
            # No crear zonas adicionales en el seed base para evitar
            # alterar el orden/selección de zonas del tenant demo.
            if not zone:
                continue
            routing_demo_zones[z_name] = zone

        # ------------------------------------------------------------------
        # Rutas draft demo para el día actual.
        # Se crean solo si existe un plan locked para esa zona
        # ------------------------------------------------------------------
        routes = {}
        route_service_date = datetime.now(UTC).date()
        active_zone_driver_vehicle = [
            ("Centro", "driver_a", "VH-001"),
            ("Costa", "driver_b", "VH-002"),
            ("Periferia", "driver_c", "VH-003"),
        ]
        for i, (z_name, drv_key, v_code) in enumerate(active_zone_driver_vehicle):
            zone_obj = routing_demo_zones.get(z_name)
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
        print("Routing POC — Flota demo:")
        print(f" - {len(vehicles)} vehículos ({sum(1 for v in vehicles.values() if v.active)} activos)")
        print(f" - {len(drivers)} choferes")
        print(f" - {len(routing_demo_zones)} zonas de referencia")
        print(f" - {len(routes)} rutas draft creadas")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
