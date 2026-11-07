import React, { useState } from "react";
import { api } from "../api.js";

export default function FieldManagement({ fields, onChanged }) {
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function renameField(field) {
    const nextName = window.prompt("Enter the new field name:", field.name);
    if (nextName === null || !nextName.trim() || nextName.trim() === field.name) return;
    setError("");
    setMessage("");
    try {
      await api.updateField(field.id, { name: nextName.trim() });
      setMessage(`${field.name} updated.`);
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="panel field-management">
      <div className="field-management__heading">
        <div>
          <h2>Registered fields</h2>
          <p>Fields and sensor nodes assigned to this farm.</p>
        </div>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {message && <p className="field-management__message" role="status">{message}</p>}
      {fields.length === 0 ? <p className="panel__empty">No fields are registered to this farm.</p> : (
        <ul className="field-management__list">
          {fields.map((field) => <li key={field.id}>
            <div><strong>{field.name}</strong><span>{field.node_id} · {field.crop}</span></div>
            <button type="button" onClick={() => renameField(field)}>Rename</button>
          </li>)}
        </ul>
      )}
    </section>
  );
}
