import React, { useCallback, useEffect, useState } from "react";
import {
  APIError,
  formatError,
  createAdminProduct,
  deactivateAdminProduct,
  listAdminProducts,
  type Product,
  updateAdminProduct,
} from "../lib/api";

type AdminProductsCardProps = {
  token: string;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function AdminProductsCard({ token }: AdminProductsCardProps) {
  const [error, setError] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [productFilter, setProductFilter] = useState<"all" | "active" | "inactive">("all");

  const [newSku, setNewSku] = useState("");
  const [newName, setNewName] = useState("");
  const [newBarcode, setNewBarcode] = useState("");
  const [newUom, setNewUom] = useState("ud");

  const [editingProductId, setEditingProductId] = useState("");
  const [editSku, setEditSku] = useState("");
  const [editName, setEditName] = useState("");
  const [editBarcode, setEditBarcode] = useState("");
  const [editUom, setEditUom] = useState("ud");

  const loadProducts = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      const active = productFilter === "all" ? undefined : productFilter === "active";
      const res = await listAdminProducts(token, { active });
      setProducts(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [token, productFilter]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  async function onCreateProduct() {
    if (!token) return;
    setError("");
    try {
      await createAdminProduct(token, {
        sku: newSku,
        name: newName,
        barcode: newBarcode || null,
        uom: newUom,
      });
      setNewSku("");
      setNewName("");
      setNewBarcode("");
      setNewUom("ud");
      await loadProducts();
    } catch (e) {
      setError(formatError(e));
    }
  }

  function startEditProduct(product: Product) {
    setEditingProductId(product.id);
    setEditSku(product.sku);
    setEditName(product.name);
    setEditBarcode(product.barcode || "");
    setEditUom(product.uom);
  }

  function cancelEdit() {
    setEditingProductId("");
    setEditSku("");
    setEditName("");
    setEditBarcode("");
    setEditUom("ud");
  }

  async function onUpdateProduct() {
    if (!token || !editingProductId) return;
    setError("");
    try {
      await updateAdminProduct(token, editingProductId, {
        sku: editSku,
        name: editName,
        barcode: editBarcode || null,
        uom: editUom,
      });
      setEditingProductId("");
      await loadProducts();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onDeactivateProduct(productId: string) {
    if (!token) return;
    setError("");
    try {
      await deactivateAdminProduct(token, productId);
      await loadProducts();
    } catch (e) {
      setError(formatError(e));
    }
  }

  return (
    <div className="admin-layout">
      {error && (
        <div className="card" style={{ backgroundColor: "var(--danger-bg)", borderColor: "var(--danger-border)" }}>
          <p style={{ margin: 0, color: "var(--danger-text)", fontWeight: "bold" }}>{error}</p>
        </div>
      )}

      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <h2 style={{ marginRight: 12 }}>Listado de Productos</h2>
          <select
            value={productFilter}
            onChange={(e) => setProductFilter(e.target.value as "all" | "active" | "inactive")}
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
          <button className="secondary" onClick={() => void loadProducts()}>
            Refrescar
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>sku</th>
              <th>nombre</th>
              <th>barcode</th>
              <th>uom</th>
              <th>estado</th>
              <th>acciones</th>
            </tr>
          </thead>
          <tbody>
            {products.length === 0 && (
              <tr>
                <td colSpan={7} style={{ color: "var(--muted)", textAlign: "center" }}>
                  Sin productos encontrados.
                </td>
              </tr>
            )}
            {products.map((product) => (
              <tr key={product.id}>
                <td>{shortId(product.id)}</td>
                <td>{product.sku}</td>
                <td>{product.name}</td>
                <td>{product.barcode ?? "—"}</td>
                <td>{product.uom}</td>
                <td>
                  <span className={product.active ? "badge ok" : "badge rejected"}>
                    {product.active ? "active" : "inactive"}
                  </span>
                </td>
                <td className="row">
                  <button className="secondary" onClick={() => startEditProduct(product)}>
                    Editar
                  </button>
                  {product.active && (
                    <button className="danger" onClick={() => void onDeactivateProduct(product.id)}>
                      Desactivar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid" style={{ gap: 12 }}>
        <div className="card grid">
          <h2>Crear Producto</h2>
          <input placeholder="SKU" value={newSku} onChange={(e) => setNewSku(e.target.value)} />
          <input placeholder="Nombre" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <input placeholder="Código de Barras (opcional)" value={newBarcode} onChange={(e) => setNewBarcode(e.target.value)} />
          <input placeholder="UOM (ej. ud, kg)" value={newUom} onChange={(e) => setNewUom(e.target.value)} />
          <button onClick={() => void onCreateProduct()}>Crear</button>
        </div>

        <div className="card grid">
          <h2>Editar Producto</h2>
          {!editingProductId && (
            <p style={{ margin: 0, color: "var(--muted)" }}>
              Selecciona un producto de la tabla para editar.
            </p>
          )}
          {editingProductId && (
            <>
              <input placeholder="SKU" value={editSku} onChange={(e) => setEditSku(e.target.value)} />
              <input placeholder="Nombre" value={editName} onChange={(e) => setEditName(e.target.value)} />
              <input placeholder="Código de Barras (opcional)" value={editBarcode} onChange={(e) => setEditBarcode(e.target.value)} />
              <input placeholder="UOM" value={editUom} onChange={(e) => setEditUom(e.target.value)} />
              <div className="row">
                <button onClick={() => void onUpdateProduct()}>Guardar</button>
                <button className="secondary" onClick={cancelEdit}>
                  Cancelar
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
