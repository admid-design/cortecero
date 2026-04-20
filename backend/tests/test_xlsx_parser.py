"""Tests para backend/app/utils/xlsx_parser.py — XLSX-PARSE-001.

Estos tests NO necesitan DB ni Docker: son unitarios puros.
Se pueden correr con:
    pytest backend/tests/test_xlsx_parser.py -v
o dentro del contenedor:
    docker compose run --rm backend pytest -q tests/test_xlsx_parser.py
"""

import io

import pytest

from app.utils.xlsx_parser import (
    TEMPLATE_FIELD_ALIASES,
    ORDER_FIELD_ALIASES,
    auto_map_columns,
    normalize_header,
    parse_csv,
    parse_day_of_week,
    parse_float,
    parse_int,
    parse_xlsx,
)


# ---------------------------------------------------------------------------
# normalize_header
# ---------------------------------------------------------------------------

class TestNormalizeHeader:
    def test_lowercase(self):
        assert normalize_header("Cliente") == "cliente"

    def test_strips_spaces(self):
        assert normalize_header("  Dirección  ") == "direccion"

    def test_removes_tilde_a(self):
        assert normalize_header("Matrícula") == "matricula"

    def test_removes_tilde_e(self):
        assert normalize_header("Teléfono") == "telefono"

    def test_removes_tilde_o(self):
        assert normalize_header("Duración") == "duracion"

    def test_removes_tilde_i(self):
        assert normalize_header("Día") == "dia"

    def test_already_normalized(self):
        assert normalize_header("lat") == "lat"

    def test_mixed_case_no_tilde(self):
        assert normalize_header("Day_Of_Week") == "day_of_week"


# ---------------------------------------------------------------------------
# auto_map_columns
# ---------------------------------------------------------------------------

class TestAutoMapColumns:
    def test_maps_exact_alias(self):
        headers = ["Matrícula", "Día", "Cliente"]
        mapping = auto_map_columns(headers, TEMPLATE_FIELD_ALIASES)
        assert mapping["vehicle_plate"] == "Matrícula"
        assert mapping["day_of_week"] == "Día"
        assert mapping["customer_name"] == "Cliente"

    def test_maps_english_alias(self):
        headers = ["Plate", "Day", "Name"]
        mapping = auto_map_columns(headers, TEMPLATE_FIELD_ALIASES)
        assert mapping["vehicle_plate"] == "Plate"
        assert mapping["day_of_week"] == "Day"
        assert mapping["customer_name"] == "Name"

    def test_ignores_unknown_columns(self):
        headers = ["Columna_Desconocida", "Matrícula"]
        mapping = auto_map_columns(headers, TEMPLATE_FIELD_ALIASES)
        assert "vehicle_plate" in mapping
        assert len(mapping) == 1

    def test_first_alias_wins(self):
        # Si el archivo tiene tanto "cliente" como "customer", gana el primero
        headers = ["customer", "cliente"]
        mapping = auto_map_columns(headers, TEMPLATE_FIELD_ALIASES)
        assert mapping["customer_name"] in ("customer", "cliente")

    def test_order_field_aliases(self):
        headers = ["Nombre", "Dirección", "Desde", "Hasta", "Referencia"]
        mapping = auto_map_columns(headers, ORDER_FIELD_ALIASES)
        assert mapping["customer_name"] == "Nombre"
        assert mapping["address"] == "Dirección"
        assert mapping["delivery_from"] == "Desde"
        assert mapping["delivery_until"] == "Hasta"
        assert mapping["external_ref"] == "Referencia"

    def test_empty_headers(self):
        mapping = auto_map_columns([], TEMPLATE_FIELD_ALIASES)
        assert mapping == {}

    def test_case_insensitive(self):
        headers = ["MATRICULA", "DIA", "CLIENTE"]
        mapping = auto_map_columns(headers, TEMPLATE_FIELD_ALIASES)
        assert mapping["vehicle_plate"] == "MATRICULA"
        assert mapping["day_of_week"] == "DIA"
        assert mapping["customer_name"] == "CLIENTE"


# ---------------------------------------------------------------------------
# parse_csv
# ---------------------------------------------------------------------------

class TestParseCsv:
    def _make_csv(self, content: str) -> bytes:
        return content.encode("utf-8")

    def test_basic_csv(self):
        csv_bytes = self._make_csv(
            "Matrícula,Día,Cliente\n"
            "6244 FKJ,Lunes,Can Biel\n"
            "7823 JBV,Martes,Es Moli\n"
        )
        rows = list(parse_csv(csv_bytes))
        assert len(rows) == 2
        assert rows[0]["Matrícula"] == "6244 FKJ"
        assert rows[0]["Día"] == "Lunes"
        assert rows[0]["Cliente"] == "Can Biel"

    def test_empty_cells_become_none(self):
        csv_bytes = self._make_csv(
            "Cliente,Dirección,Lat\n"
            "Can Biel,,\n"
        )
        rows = list(parse_csv(csv_bytes))
        assert rows[0]["Dirección"] is None
        assert rows[0]["Lat"] is None

    def test_skips_blank_rows(self):
        csv_bytes = self._make_csv(
            "Cliente,Dirección\n"
            "Can Biel,Carrer Major\n"
            ",,\n"
            "Es Moli,Plaça Vila\n"
        )
        rows = list(parse_csv(csv_bytes))
        assert len(rows) == 2

    def test_empty_file(self):
        csv_bytes = self._make_csv("Cliente,Dirección\n")
        rows = list(parse_csv(csv_bytes))
        assert rows == []

    def test_latin1_fallback(self):
        # Archivo con codificación latin-1 (frecuente en XLS exportados)
        content = "Matrícula,Cliente\n6244 FKJ,Café\n"
        csv_bytes = content.encode("latin-1")
        rows = list(parse_csv(csv_bytes))
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# parse_xlsx — requiere openpyxl
# ---------------------------------------------------------------------------

def _make_xlsx_bytes(rows: list[list]) -> bytes:
    """Helper: crea un .xlsx en memoria con las filas dadas (primera = cabeceras)."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseXlsx:
    def test_basic_xlsx(self):
        xlsx = _make_xlsx_bytes([
            ["Matrícula", "Día", "Cliente"],
            ["6244 FKJ", "Lunes", "Can Biel"],
            ["7823 JBV", "Martes", "Es Moli"],
        ])
        rows = list(parse_xlsx(xlsx))
        assert len(rows) == 2
        assert rows[0]["Matrícula"] == "6244 FKJ"
        assert rows[1]["Cliente"] == "Es Moli"

    def test_empty_cells_become_none(self):
        xlsx = _make_xlsx_bytes([
            ["Cliente", "Lat", "Lng"],
            ["Can Biel", None, None],
        ])
        rows = list(parse_xlsx(xlsx))
        assert rows[0]["Lat"] is None
        assert rows[0]["Lng"] is None

    def test_skips_blank_rows(self):
        xlsx = _make_xlsx_bytes([
            ["Cliente", "Dirección"],
            ["Can Biel", "Carrer Major"],
            [None, None],
            ["Es Moli", "Plaça Vila"],
        ])
        rows = list(parse_xlsx(xlsx))
        assert len(rows) == 2

    def test_invalid_file_raises_value_error(self):
        with pytest.raises(ValueError, match="XLSX"):
            list(parse_xlsx(b"esto no es un xlsx"))

    def test_empty_file(self):
        xlsx = _make_xlsx_bytes([["Cliente", "Dirección"]])
        rows = list(parse_xlsx(xlsx))
        assert rows == []

    def test_numeric_cells_converted_to_str(self):
        xlsx = _make_xlsx_bytes([
            ["Secuencia", "Duración"],
            [1, 15],
        ])
        rows = list(parse_xlsx(xlsx))
        assert rows[0]["Secuencia"] == "1"
        assert rows[0]["Duración"] == "15"


# ---------------------------------------------------------------------------
# parse_day_of_week
# ---------------------------------------------------------------------------

class TestParseDayOfWeek:
    @pytest.mark.parametrize("value,expected", [
        ("1", 1),
        ("7", 7),
        ("Lunes", 1),
        ("lunes", 1),
        ("LUNES", 1),
        ("Lun", 1),
        ("Monday", 1),
        ("Mon", 1),
        ("Martes", 2),
        ("Miércoles", 3),
        ("Miercoles", 3),
        ("Jueves", 4),
        ("Viernes", 5),
        ("Sábado", 6),
        ("Domingo", 7),
        ("Saturday", 6),
        ("Sunday", 7),
    ])
    def test_valid_values(self, value, expected):
        assert parse_day_of_week(value) == expected

    @pytest.mark.parametrize("value", [None, "", "Someday", "8", "0", "abc"])
    def test_invalid_values_return_none(self, value):
        assert parse_day_of_week(value) is None


# ---------------------------------------------------------------------------
# parse_float / parse_int
# ---------------------------------------------------------------------------

class TestParseFloat:
    def test_dot_decimal(self):
        assert parse_float("39.6578") == pytest.approx(39.6578)

    def test_comma_decimal(self):
        assert parse_float("39,6578") == pytest.approx(39.6578)

    def test_none_returns_none(self):
        assert parse_float(None) is None

    def test_non_numeric_returns_none(self):
        assert parse_float("abc") is None


class TestParseInt:
    def test_integer_string(self):
        assert parse_int("10") == 10

    def test_float_string_truncates(self):
        assert parse_int("10.9") == 10

    def test_none_returns_none(self):
        assert parse_int(None) is None

    def test_non_numeric_returns_none(self):
        assert parse_int("abc") is None
