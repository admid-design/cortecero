import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AdminProductsCard } from "../components/AdminProductsCard";

test("renders empty state and forms for AdminProductsCard", () => {
  const html = renderToStaticMarkup(<AdminProductsCard token="dummy-token" />);
  
  assert.match(html, /Listado de Productos/);
  assert.match(html, /Crear Producto/);
  assert.match(html, /Editar Producto/);
  
  // Table headers
  assert.match(html, /sku/);
  assert.match(html, /nombre/);
  assert.match(html, /barcode/);
  assert.match(html, /uom/);
  assert.match(html, /estado/);

  // Empty state explicitly handled
  assert.match(html, /Sin productos encontrados\./);
});
