import React, { useState } from "react";
import { api } from "../api.js";

export default function FieldManagement({ fields, onChanged }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [crop, setCrop] = useState("maize");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function addField(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.createField({ name: name.trim(), node_id: nodeId.trim(), crop });
      setName("");
      setNodeId("");
      setCrop("maize");
      setOpen(false);
      setMessage("Field added successfully.");
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
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
          <h2>Farm fields</h2>
          <p>Manage the plots and sensor nodes registered to this farm.</p>
        </div>
        <button className="field-management__add" onClick={() => setOpen((value) => !value)}>
          {open ? "Cancel" : "Add field"}
        </button>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {message && <p className="field-management__message" role="status">{message}</p>}
      {open && <form className="field-management__form" onSubmit={addField}>
        <label>Field name<input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} placeholder="e.g. North Plot" /></label>
        <label>Sensor node ID<input value={nodeId} onChange={(e) => setNodeId(e.target.value)} required maxLength={32} pattern="[A-Za-z0-9_-]+" placeholder="e.g. node-05" /></label>
        <label>Crop<input value={crop} onChange={(e) => setCrop(e.target.value)} required maxLength={40} /></label>
        <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Adding..." : "Save field"}</button>
      </form>}
      {fields.length === 0 ? <p className="panel__empty">No fields registered yet.</p> : (
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
