import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.config import settings
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

        # ── Catálogo de productos demo ────────────────────────────────────────────
        # Estructura basada en distribución real de higiene/limpieza industrial.
        # Códigos y descripciones sintéticos; sin datos reales.
        # (code, descripción, peso_kg, volumen_m3)
        _product_catalog = [
            # Papel e higiene básica
            ("PPL-001", "Bobina Secamanos Industrial 6 uds.",          3.0,  0.030),
            ("PPL-002", "Higiénico Doméstico 2C 108 rollos",          12.0,  0.120),
            ("PPL-003", "Servilleta 30x30 Blanca 1.000 uds.",          2.5,  0.025),
            ("PPL-004", "Toalla Entrelazada PP 3.800 uds.",            4.0,  0.040),
            # Plásticos y limpieza básica
            ("PLB-001", "Bolsa Basura 52x58 Neg. R.25",                6.0,  0.050),
            ("PLB-002", "Bolsa Basura 85x105 Neg. R.10",              10.0,  0.080),
            ("PLB-003", "Fregona Microfibra Blanco/Azul",              1.5,  0.015),
            ("PLB-004", "Recogedor Antivuelco con Palo",               0.8,  0.010),
            ("PLB-005", "Escobilla WC Plástico + Soporte",             0.5,  0.005),
            # Química industrial
            ("QIM-001", "Lejía 5 L. (Hipoclorito Sodio)",             5.5,  0.006),
            ("QIM-002", "Lejía 21 L. (Hipoclorito Sodio)",           22.0,  0.022),
            ("QIM-003", "Desengrasante Industrial 6 kg.",              6.0,  0.006),
            ("QIM-004", "Limpiador Suelos Concentrado 5 L.",           5.5,  0.006),
            ("QIM-005", "Detergente Lavavajillas Industrial 24 kg.",  24.0,  0.025),
            ("QIM-006", "Abrillantador Suelos 21 kg.",                21.0,  0.022),
            # Higiene personal y EPIs
            ("HIG-001", "Gel de Manos 5 L.",                          5.2,  0.006),
            ("HIG-002", "Guante Nitrilo Azul T/M 100 uds.",           0.8,  0.005),
            ("HIG-003", "Guante Nitrilo Negro T/G 100 uds.",          0.9,  0.005),
            ("HIG-004", "Estropajo Fibra Verde 6 mts.",               0.3,  0.003),
            # Piscinas (químicos ADR)
            ("PSC-001", "Piscina pH- Minorador 24 kg.",              24.0,  0.025),
            ("PSC-002", "Piscina Hipoclorito Sodio 25 kg.",          25.0,  0.026),
            ("PSC-003", "Piscina Antialgas 25 kg.",                   25.0,  0.026),
            ("PSC-004", "Piscina Bromo Pastillas 5 kg.",               5.5,  0.006),
            # Servicio técnico / SAT
            ("SAT-001", "Kit Mantenimiento Instalaciones",             2.0,  0.010),
            ("SAT-002", "Recambio Técnico Genérico",                  1.5,  0.008),
        ]

        # Productos asignados por tipo de cliente (índices en _product_catalog).
        # Representa la cesta de productos habitual de cada sector.
        _products_by_biz: dict[str, list[int]] = {
            "hotel":       [0, 1, 3, 9, 11, 12, 15, 16, 17, 19, 20, 21],
            "restaurant":  [0, 2, 3, 4, 5, 9, 11, 12, 16, 17, 18],
            "clinic":      [0, 1, 2, 9, 15, 16, 17, 18, 23],
            "supermarket": [1, 4, 5, 6, 9, 15, 16],
            "facility":    [0, 3, 4, 5, 6, 10, 11, 12, 13, 16, 17],
            "hotel_pool":  [0, 1, 9, 15, 16, 19, 20, 21, 22, 23, 24],
        }

        # Dataset geográfico + tipo de negocio. Sin datos reales de cliente.
        # Formato: (nombre_demo, lat, lng, dirección_demo, tipo_negocio)
        # Cobertura: Palma, Costa Nord, Costa Llevant, Interior, Sud.
        # Zonas representativas de rutas invierno (3 zonas) y verano (7 zonas).
        _customer_data = [
            # Centro (zone_a) — Palma de Mallorca
            ("Hotel Demo Mediterráneo",          39.5711, 2.6512, "Avinguda Jaume III 1, Palma",            "hotel_pool"),
            ("Restaurante Demo Son Blai",        39.5752, 2.6478, "Carrer de Sant Miquel 2, Palma",         "restaurant"),
            ("Clínica Demo Llevant",             39.5688, 2.6551, "Passeig del Born 3, Palma",              "clinic"),
            ("Supermercado Demo Centre",         39.5730, 2.6590, "Carrer de Colom 4, Palma",               "supermarket"),
            ("Facility Services Demo Sur",       39.5660, 2.6440, "Avinguda Argentina 5, Palma",            "facility"),
            # Costa Nord — Alcúdia, Pollença, Can Picafort
            ("Hotel Demo Costa Nord",            39.8517, 3.1191, "Carrer Major 6, Alcúdia",                "hotel_pool"),
            ("Resort Demo Pollença",             39.8789, 3.0157, "Port de Pollença 7, Pollença",           "hotel"),
            ("Hotel Demo Can Picafort",          39.7641, 3.1649, "Passeig de la Mare de Déu 8, Can Picafort", "hotel_pool"),
            # Costa Llevant — Manacor, Porto Cristo, Cala Millor
            ("Resort Demo Llevant",              39.7064, 3.2030, "Avinguda del Parc 9, Manacor",           "hotel"),
            ("Hotel Demo Cala Millor",           39.5909, 3.3684, "Carrer Na Penyal 10, Cala Millor",       "hotel_pool"),
            # Interior — Inca, Algaida, Sineu
            ("Clínica Demo Interior",            39.7208, 2.9133, "Gran Via de Colom 11, Inca",             "clinic"),
            ("Facility Services Demo Algaida",   39.5673, 2.8947, "Carretera Manacor 12, Algaida",          "facility"),
            ("Supermercado Demo Sineu",          39.6431, 3.0123, "Plaça de Son Fornés 13, Sineu",          "supermarket"),
            # Costa Sud — Llucmajor, S'Arenal, Campos
            ("Hostelería Demo S'Arenal",         39.4997, 2.7434, "Carrer de l'Arenal 14, Llucmajor",      "restaurant"),
            ("Facility Services Demo Campos",    39.4274, 3.0148, "Carrer de Felanitx 15, Campos",         "facility"),
        ]
        # Nombres legacy (antes del dataset realista) — para backfill sin duplicados.
        _legacy_customer_names = [f"Cliente {i + 1:02d}" for i in range(15)]

        customers = []
        for idx in range(15):
            zone = zone_a if idx < 5 else zone_b  # 5 Palma (Centro), 10 isla (Costa)
            new_name, lat_val, lng_val, addr, biz_type = _customer_data[idx]
            legacy_name = _legacy_customer_names[idx]

            # Busca por nombre nuevo primero, luego por nombre legacy (migración).
            customer = db.scalar(
                select(Customer).where(Customer.tenant_id == tenant.id, Customer.name == new_name)
            ) or db.scalar(
                select(Customer).where(Customer.tenant_id == tenant.id, Customer.name == legacy_name)
            )

            if not customer:
                customer = Customer(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    zone_id=zone.id,
                    name=new_name,
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
                # Backfill: nombre, coordenadas y zona a los valores canónicos.
                needs_update = False
                if customer.name != new_name:
                    customer.name = new_name
                    needs_update = True
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

        service_date = datetime.now(ZoneInfo("Europe/Madrid")).date()

        existing_orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date)))
        if len(existing_orders) < 30:
            for idx in range(30):
                customer = customers[idx % len(customers)]
                _, lat_val, lng_val, addr, biz_type = _customer_data[idx % len(_customer_data)]
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
                created_at = effective_cutoff - timedelta(hours=2) if idx < 20 else effective_cutoff + timedelta(hours=1)
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

                # ── OrderLines: múltiples productos por pedido ────────────────
                # Selección determinista basada en tipo de cliente e índice.
                # Simula la cesta real (2-6 líneas, pesos realistas por categoría).
                product_indices = _products_by_biz.get(biz_type, _products_by_biz["facility"])
                n_lines = 3 + (idx % 4)  # 3-6 líneas por pedido
                for line_idx in range(n_lines):
                    prod_idx = product_indices[(idx * 3 + line_idx) % len(product_indices)]
                    sku, desc, wkg, vm3 = _product_catalog[prod_idx]
                    qty = 1 + ((idx + line_idx * 2) % 5)  # 1-5 unidades
                    db.add(
                        OrderLine(
                            id=uuid.uuid4(),
                            tenant_id=tenant.id,
                            order_id=order.id,
                            sku=sku,
                            qty=float(qty),
                            weight_kg=round(wkg * qty, 2),
                            volume_m3=round(vm3 * qty, 4),
                            created_at=now_utc(),
                        )
                    )

        # ── Reset demo: asegura pedidos visibles en la cola ──────────────────────
        # Corre siempre en cold start. La protección real está en el loop:
        # solo se resetean pedidos en estado 'planned' que NO tienen RouteStop
        # asignado — los pedidos de rutas activas están protegidos por has_stop.
        all_today_orders = list(
            db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date))
        )
        queueable_today = [o for o in all_today_orders if o.status == OrderStatus.ready_for_planning]
        if len(queueable_today) < 5:
            for o in all_today_orders:
                if o.status == OrderStatus.planned:
                    has_stop = db.scalar(
                        select(RouteStop).where(
                            RouteStop.tenant_id == tenant.id,
                            RouteStop.order_id == o.id,
                        )
                    )
                    if not has_stop:
                        plan_order_rec = db.scalar(
                            select(PlanOrder).where(
                                PlanOrder.tenant_id == tenant.id,
                                PlanOrder.order_id == o.id,
                            )
                        )
                        if plan_order_rec:
                            db.delete(plan_order_rec)
                        o.status = OrderStatus.ready_for_planning
                        o.updated_at = now_utc()
            db.flush()

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

        # Plan para mañana (zone_a, open) — requerido por test_plans_auto_lock.
        # La función de auto-lock bloquea planes del día siguiente al ejecutarse;
        # sin este plan el seed no provee datos suficientes para ese contrato.
        tomorrow = service_date + timedelta(days=1)
        tomorrow_plan = db.scalar(
            select(Plan).where(
                Plan.tenant_id == tenant.id,
                Plan.service_date == tomorrow,
                Plan.zone_id == zone_a.id,
            )
        )
        if not tomorrow_plan:
            db.add(Plan(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                service_date=tomorrow,
                zone_id=zone_a.id,
                status=PlanStatus.open,
                version=1,
                locked_at=None,
                locked_by=None,
                created_at=now_utc(),
                updated_at=now_utc(),
            ))
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

        pending_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-029")
        approved_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-030")
        rejected_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-028")

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
        # Vehículos demo — 12 unidades, estructura idéntica a la flota real.
        # Capacidades verificadas desde ficha de flota operativa.
        # Códigos y nombres sintéticos; sin matrículas reales.
        #
        # Notas operativas (solo para referencia interna; no en UI):
        #   VH-005: restricción ZBE activa (sin etiqueta ambiental) → rutas fuera de ciudad
        #   VH-012: restricción ZBE desde 2027 (etiqueta B) → activo hasta entonces
        #   VH-010, VH-011, VH-012: vehículos de reserva / rotación secundaria
        # ------------------------------------------------------------------
        vehicles = {}
        for code, name, capacity in [
            # Camiones — carnet C obligatorio
            ("VH-001", "Camión Demo 14T",         7580.0),  # IVECO ML140E22
            ("VH-002", "Camión Demo 12T",         6145.0),  # DAF
            ("VH-003", "Camión Demo 10T",         4975.0),  # IVECO ML100E22
            ("VH-004", "Camión Demo 9T-A",        4150.0),  # IVECO ML90E18
            ("VH-005", "Camión Demo 9T-B [ZBE]",  3460.0),  # IVECO ML90E18 2003 – ZBE prohibido
            # Furgones grandes — carnet B (o C)
            ("VH-006", "Furgón Demo 8T",          2000.0),  # RENAULT Cartemet
            ("VH-007", "Furgón Demo 7T",          2600.0),  # IVECO Euro 5
            # Furgones medianos — carnet B
            ("VH-008", "Furgón Demo 3.5T-A",      1502.0),  # IVECO C50A10
            ("VH-009", "Furgón Demo 3.5T-B",      1342.0),  # IVECO C35730 Euro 5
            # Reserva / rotación secundaria
            ("VH-010", "Furgón Demo 3.5T-C",       860.0),  # IVECO C35730 2007
            ("VH-011", "Furgón Demo 2T",            660.0),  # FORD Transit Connect
            ("VH-012", "Furgón Demo Pequeño",       290.0),  # RENAULT Kangoo – ZBE 2027
        ]:
            vehicle = db.scalar(select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.code == code))
            if not vehicle:
                vehicle = Vehicle(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    code=code,
                    name=name,
                    capacity_kg=capacity,
                    # VH-010/011/012: reserva/rotación secundaria — inactivos por defecto.
                    active=(code not in ("VH-010", "VH-011", "VH-012")),
                    created_at=now_utc(),
                )
                db.add(vehicle)
                db.flush()
            else:
                # Backfill: actualiza nombre y capacidad a los valores canónicos.
                if vehicle.name != name:
                    vehicle.name = name
                if vehicle.capacity_kg != capacity:
                    vehicle.capacity_kg = capacity
                # Reactiva vehículos que estaban incorrectamente inactivos (VH-005..009).
                if code not in ("VH-010", "VH-011", "VH-012") and not vehicle.active:
                    vehicle.active = True
            vehicles[code] = vehicle

        # ------------------------------------------------------------------
        # Conductores demo — 8 conductores, estructura basada en flota real.
        # Tipo de carnet y ADR codificados en el nombre para visibilidad en demo.
        # Sin nombres reales; teléfonos sintéticos.
        #
        # Distribución real replicada:
        #   Carnet C + ADR (4): camiones VH-001..004
        #   Carnet B + ADR (3): furgones VH-006, VH-007, VH-009
        #   Carnet B sin ADR (1): furgones solo rutas no-ADR (VH-008)
        # ------------------------------------------------------------------
        drivers = {}
        for drv_key, name, phone, vehicle_code in [
            # Camioneros — carnet C + ADR
            ("driver_a", "Conductor Demo A (C·ADR)", "700000101", "VH-001"),
            ("driver_b", "Conductor Demo B (C·ADR)", "700000102", "VH-002"),
            ("driver_c", "Conductor Demo C (C·ADR)", "700000103", "VH-003"),
            ("driver_d", "Conductor Demo D (C·ADR)", "700000104", "VH-004"),
            # Furgoneros — carnet B + ADR
            ("driver_e", "Conductor Demo E (B·ADR)", "700000105", "VH-006"),
            ("driver_f", "Conductor Demo F (B·ADR)", "700000106", "VH-007"),
            ("driver_h", "Conductor Demo H (B·ADR)", "700000108", "VH-009"),
            # Furgonero — carnet B sin ADR (solo rutas no-químicas)
            ("driver_g", "Conductor Demo G (B)",     "700000107", "VH-008"),
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
            else:
                # Backfill: actualiza nombre si cambia formato canónico.
                if driver.name != name:
                    driver.name = name
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
        route_service_date = service_date  # mismo día que los pedidos
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
        print(f"Fecha de servicio: {service_date}")
        print("Users:")
        print(" - office@demo.cortecero.app / office123")
        print(" - logistics@demo.cortecero.app / logistics123")
        print(" - admin@demo.cortecero.app / admin123")
        final_orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date)))
        print(f"Pedidos en cola (ready_for_planning): {len([o for o in final_orders if o.status == OrderStatus.ready_for_planning])}")
        print(f"Pedidos totales hoy: {len(final_orders)}")
        print("Flota demo:")
        print(f" - {len(vehicles)} vehículos ({sum(1 for v in vehicles.values() if v.active)} en rotación activa)")
        print(f" - {len(drivers)} conductores (4×C·ADR, 3×B·ADR, 1×B)")
        print(f" - {len(routing_demo_zones)} zonas de ruteo")
        print(f" - {len(routes)} rutas draft creadas")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
