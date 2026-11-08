import React, { useState } from "react";
import { api } from "../api.js";
import CopyField from "./CopyField.jsx";

export default function FieldManagement({ fields, onChanged }) {
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [issued, setIssued] = useState(null);

  async function issueKey(field) {
    const replacing = field.has_node_key;
    if (replacing && !window.confirm(`Issue a new key for ${field.name}? The sensor stops reporting until you put the new key on it.`)) return;
    setError("");
    setMessage("");
    try {
      setIssued(await api.issueNodeKey(field.id));
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

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
      {issued && (
        <div className="invite-reveal" role="status">
          <p><strong>Sensor key for {issued.node_id}.</strong> It is shown only once. Put it on the device as the <code>X-Node-Key</code> header, or save it in the simulator's <code>node_keys.json</code>. Any earlier key for this sensor no longer works.</p>
          <CopyField label="Sensor key" value={issued.node_key} />
          <button type="button" className="invite-reveal__done" onClick={() => setIssued(null)}>Done</button>
        </div>
      )}
      {fields.length === 0 ? <p className="panel__empty">No fields are registered to this farm.</p> : (
        <ul className="field-management__list">
          {fields.map((field) => <li key={field.id}>
            <div><strong>{field.name}</strong><span>{field.node_id} · {field.crop} · {field.has_node_key ? "key issued" : "no key yet, readings are rejected"}</span></div>
            <div className="field-management__buttons">
              <button type="button" onClick={() => issueKey(field)}>{field.has_node_key ? "New key" : "Issue key"}</button>
              <button type="button" onClick={() => renameField(field)}>Rename</button>
            </div>
          </li>)}
        </ul>
      )}
    </section>
  );
}
