"""Parser XLSX/CSV reutilizable para importación de datos.

XLSX-PARSE-001 — CorteCero R10

Responsabilidades:
- Parsear archivos .xlsx y .csv en memoria (bytes) sin tocar disco.
- Normalizar cabeceras: minúsculas, sin tildes, sin espacios extremos.
- Autodetectar columnas por tabla de alias configurable.
- Exponer una API sencilla: parse_xlsx() → Generator[dict, None, None]

Dependencias: openpyxl (solo stdlib + openpyxl; no pandas).
"""

from __future__ import annotations

import csv
import io
import unicodedata
from typing import Generator


# ---------------------------------------------------------------------------
# Normalización de nombres de columna
# ---------------------------------------------------------------------------

def normalize_header(name: str) -> str:
    """Normaliza un nombre de columna para comparación case-insensitive y sin tildes.

    Ejemplos:
        "Matrícula"  → "matricula"
        "Dirección"  → "direccion"
        "  Cliente " → "cliente"
        "Day_Of_Week" → "day_of_week"
    """
    # Eliminar espacios extremos
    name = name.strip()
    # NFD descompone los caracteres acentuados en base + diacrítico
    nfd = unicodedata.normalize("NFD", name)
    # Filtrar los diacríticos (categoría Mn = Mark, Nonspacing)
    without_accents = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return without_accents.lower()


# ---------------------------------------------------------------------------
# Tablas de alias por campo
# ---------------------------------------------------------------------------

# Campos para importación de PLANTILLAS DE RUTA (Tipo B)
TEMPLATE_FIELD_ALIASES: dict[str, list[str]] = {
    "vehicle_plate": ["matricula", "plate", "vehiculo", "vehicle", "camion", "truck"],
    "day_of_week":   ["dia", "day", "dia_semana", "day_of_week", "weekday"],
    "sequence":      ["orden", "sequence", "seq", "parada", "stop", "parada#", "stop#", "posicion"],
    "customer_name": ["cliente", "customer", "name", "nombre", "destinatario"],
    "address":       ["direccion", "address", "dir", "domicilio"],
    "lat":           ["lat", "latitude", "latitud"],
    "lng":           ["lng", "lon", "longitude", "longitud"],
    "duration_min":  ["duration", "duracion", "tiempo", "minutos", "stop_time", "service_time"],
    "notes":         ["notas", "notes", "observaciones", "obs", "comentarios"],
    "template_name": ["plantilla", "template", "ruta", "route", "nombre_ruta"],
}

# Campos para importación de PEDIDOS (Tipo A)
ORDER_FIELD_ALIASES: dict[str, list[str]] = {
    "customer_name":  ["cliente", "customer", "name", "nombre", "destinatario"],
    "address":        ["direccion", "address", "dir", "domicilio"],
    "lat":            ["lat", "latitude", "latitud"],
    "lng":            ["lng", "lon", "longitude", "longitud"],
    "delivery_from":  ["delivery_start", "desde", "from", "time_from", "hora_desde", "ventana_inicio"],
    "delivery_until": ["delivery_end", "hasta", "until", "time_to", "hora_hasta", "ventana_fin"],
    "duration_min":   ["duration", "duracion", "stop_time", "minutos"],
    "load_kg":        ["load", "weight", "peso", "capacidad", "kg"],
    "external_ref":   ["reference", "ref", "pedido", "order_id", "order_ref", "referencia"],
    "notes":          ["notas", "notes", "observaciones", "obs", "comentarios"],
}


def auto_map_columns(
    headers: list[str],
    field_aliases: dict[str, list[str]],
) -> dict[str, str]:
    """Mapea cabeceras detectadas a campos canónicos usando la tabla de alias.

    Retorna un dict {campo_canonico: cabecera_original}.
    Si una cabecera no coincide con ningún alias, se ignora silenciosamente.
    Si un campo tiene múltiples cabeceras candidatas, gana la primera.

    Args:
        headers: cabeceras tal como aparecen en el archivo (sin normalizar).
        field_aliases: tabla de alias por campo canónico.

    Returns:
        Mapping campo_canonico → cabecera_original del archivo.
    """
    # Normalizar cabeceras del archivo una sola vez
    normalized_map: dict[str, str] = {normalize_header(h): h for h in headers}

    mapping: dict[str, str] = {}
    for field, aliases in field_aliases.items():
        for alias in aliases:
            norm_alias = normalize_header(alias)
            if norm_alias in normalized_map:
                mapping[field] = normalized_map[norm_alias]
                break  # primera coincidencia gana

    return mapping


# ---------------------------------------------------------------------------
# Parsing de archivos
# ---------------------------------------------------------------------------

def parse_xlsx(file_bytes: bytes) -> Generator[dict[str, str | None], None, None]:
    """Parsea un archivo .xlsx y genera una fila por dict con cabeceras como claves.

    Las celdas vacías se representan como None.
    Se saltan filas completamente vacías.

    Args:
        file_bytes: contenido binario del archivo .xlsx.

    Yields:
        dict con {cabecera: valor_str_o_None} por cada fila de datos.

    Raises:
        ValueError: si el archivo no puede parsearse como .xlsx.
    """
    try:
        import openpyxl  # import lazy — solo cuando se necesita
    except ImportError as exc:
        raise RuntimeError("openpyxl no está instalado. Añádelo a requirements.txt.") from exc

    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes),
            read_only=True,
            data_only=True,
        )
    except Exception as exc:
        raise ValueError(f"No se pudo abrir el archivo como XLSX: {exc}") from exc

    ws = wb.active
    rows = ws.iter_rows(values_only=True)

    # Primera fila = cabeceras
    try:
        raw_headers = next(rows)
    except StopIteration:
        return  # archivo vacío

    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(raw_headers)]

    for raw_row in rows:
        # Saltar filas completamente vacías
        if all(cell is None or str(cell).strip() == "" for cell in raw_row):
            continue

        row_dict: dict[str, str | None] = {}
        for header, cell in zip(headers, raw_row):
            if cell is None or str(cell).strip() == "":
                row_dict[header] = None
            else:
                row_dict[header] = str(cell).strip()

        yield row_dict

    wb.close()


def parse_csv(file_bytes: bytes, encoding: str = "utf-8") -> Generator[dict[str, str | None], None, None]:
    """Parsea un archivo .csv y genera una fila por dict con cabeceras como claves.

    Intenta UTF-8 primero; si falla, reintenta con latin-1.

    Args:
        file_bytes: contenido binario del archivo .csv.
        encoding: codificación a usar (por defecto utf-8).

    Yields:
        dict con {cabecera: valor_str_o_None} por cada fila de datos.
    """
    try:
        text = file_bytes.decode(encoding)
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        # Normalizar celdas vacías a None
        cleaned = {k: (v.strip() if v and v.strip() else None) for k, v in row.items()}
        # Saltar filas completamente vacías
        if all(v is None for v in cleaned.values()):
            continue
        yield cleaned


def parse_file(
    file_bytes: bytes,
    filename: str,
) -> Generator[dict[str, str | None], None, None]:
    """Punto de entrada unificado: detecta .xlsx o .csv por extensión del nombre.

    Args:
        file_bytes: contenido binario del archivo.
        filename: nombre original del archivo (usado para detectar extensión).

    Yields:
        dict con {cabecera: valor_str_o_None} por cada fila de datos.

    Raises:
        ValueError: si la extensión no es .xlsx ni .csv.
    """
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        yield from parse_xlsx(file_bytes)
    elif lower.endswith(".csv"):
        yield from parse_csv(file_bytes)
    else:
        raise ValueError(f"Formato no soportado: '{filename}'. Se acepta .xlsx y .csv")


# ---------------------------------------------------------------------------
# Helpers de conversión de valores
# ---------------------------------------------------------------------------

DAY_NAME_MAP: dict[str, int] = {
    # Español
    "lunes": 1, "martes": 2, "miercoles": 3, "miércoles": 3,
    "jueves": 4, "viernes": 5, "sabado": 6, "sábado": 6, "domingo": 7,
    # Abreviados ES
    "lun": 1, "mar": 2, "mie": 3, "jue": 4, "vie": 5, "sab": 6, "dom": 7,
    # Inglés
    "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
    "friday": 5, "saturday": 6, "sunday": 7,
    # Abreviados EN
    "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7,
}


def parse_day_of_week(value: str | None) -> int | None:
    """Convierte un valor de día de la semana a entero ISO (1=Lun … 7=Dom).

    Acepta:
    - Número directo: "1" → 1
    - Nombre ES/EN: "Lunes" → 1, "Monday" → 1
    - Abreviatura ES/EN: "Lun" → 1, "Mon" → 1

    Retorna None si el valor no puede parsearse.
    """
    if value is None:
        return None
    stripped = value.strip()
    # Intentar como número
    try:
        n = int(stripped)
        if 1 <= n <= 7:
            return n
    except ValueError:
        pass
    # Intentar como nombre
    key = normalize_header(stripped)
    return DAY_NAME_MAP.get(key)


def parse_float(value: str | None) -> float | None:
    """Convierte un valor de texto a float, aceptando comas como separador decimal."""
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def parse_int(value: str | None) -> int | None:
    """Convierte un valor de texto a int."""
    if value is None:
        return None
    try:
        return int(float(value.replace(",", ".")))
    except (ValueError, AttributeError):
        return None
