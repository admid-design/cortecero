import React from "react";
import type { ExceptionItem } from "../lib/api";

type ExceptionsTableCardProps = {
  exceptionOrderId: string;
  onExceptionOrderIdChange: (value: string) => void;
  exceptionNote: string;
  onExceptionNoteChange: (value: string) => void;
  onCreateException: () => void;
  exceptions: ExceptionItem[];
  onApproveException: (exceptionId: string) => void;
  onRejectException: (exceptionId: string) => void;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function ExceptionsTableCard({
  exceptionOrderId,
  onExceptionOrderIdChange,
  exceptionNote,
  onExceptionNoteChange,
  onCreateException,
  exceptions,
  onApproveException,
  onRejectException,
}: ExceptionsTableCardProps) {
  return (
    <div className="card grid exceptions-table-card">
      <h2>Excepciones</h2>
      <div className="row">
        <input placeholder="order_id" value={exceptionOrderId} onChange={(e) => onExceptionOrderIdChange(e.target.value)} />
        <input placeholder="nota" value={exceptionNote} onChange={(e) => onExceptionNoteChange(e.target.value)} />
        <button className="warn" onClick={onCreateException}>
          Solicitar excepción
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>id</th>
            <th>order</th>
            <th>estado</th>
            <th>acción</th>
          </tr>
        </thead>
        <tbody>
          {exceptions.map((item) => (
            <tr key={item.id}>
              <td>{shortId(item.id)}</td>
              <td>{shortId(item.order_id)}</td>
              <td>{item.status}</td>
              <td className="row">
                {item.status === "pending" && (
                  <>
                    <button onClick={() => onApproveException(item.id)}>Aprobar</button>
                    <button className="danger" onClick={() => onRejectException(item.id)}>
                      Rechazar
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
