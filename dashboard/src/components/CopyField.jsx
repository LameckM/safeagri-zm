import React, { useState } from "react";

// navigator.clipboard only exists on https or localhost, and the dashboard is often
// opened over plain http on the farm network, so fall back to the old copy command.
async function copyText(text) {
  try {
    if (window.isSecureContext && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* fall through to the fallback */ }
  const box = document.createElement("textarea");
  box.value = text;
  box.setAttribute("readonly", "");
  box.style.position = "fixed";
  box.style.opacity = "0";
  document.body.appendChild(box);
  box.select();
  let copied = false;
  try { copied = document.execCommand("copy"); } catch { copied = false; }
  document.body.removeChild(box);
  return copied;
}

export default function CopyField({ label, value }) {
  const [state, setState] = useState("");
  async function copy() {
    setState((await copyText(value)) ? "Copied" : "Press and hold the text to copy");
    setTimeout(() => setState(""), 2500);
  }
  return (
    <div className="copy-field">
      <label>{label}
        <input readOnly value={value} onFocus={(event) => event.target.select()} />
      </label>
      <button type="button" onClick={copy}>{state === "Copied" ? "Copied" : "Copy"}</button>
      {state && state !== "Copied" && <span className="copy-field__note">{state}</span>}
    </div>
  );
}
