import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import CopyField from "./CopyField.jsx";

function dateLabel(iso) {
  return new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

export default function TeamPanel() {
  const [invites, setInvites] = useState([]);
  const [fresh, setFresh] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setInvites(await api.invites());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function create() {
    setBusy(true);
    setError("");
    try {
      setFresh(await api.createInvite());
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(invite) {
    setError("");
    try {
      await api.revokeInvite(invite.id);
      if (fresh?.id === invite.id) setFresh(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const link = fresh ? `${window.location.origin}${window.location.pathname}?invite=${encodeURIComponent(fresh.invite_code)}` : "";

  return (
    <section className="panel team-panel">
      <div className="team-panel__heading">
        <div>
          <h2>Team</h2>
          <p>Invite someone to see this farm's fields, alerts and irrigation history. Each invite works for one person.</p>
        </div>
        <button type="button" className="team-panel__create" onClick={create} disabled={busy}>
          {busy ? "Creating..." : "Create invite"}
        </button>
      </div>

      {error && <p className="auth-error" role="alert">{error}</p>}

      {fresh && (
        <div className="invite-reveal" role="status">
          <p><strong>Share this with the person joining.</strong> It is shown only once and expires on {dateLabel(fresh.expires_at)}.</p>
          <CopyField label="Invite link" value={link} />
          <CopyField label="Invite code" value={fresh.invite_code} />
          <button type="button" className="invite-reveal__done" onClick={() => setFresh(null)}>Done</button>
        </div>
      )}

      {invites.length === 0 ? <p className="panel__empty">No invitations yet.</p> : (
        <ul className="invite-list">
          {invites.map((invite) => (
            <li key={invite.id}>
              <div>
                <span className={`invite-status invite-status--${invite.status}`}>{invite.status}</span>
                <span className="invite-list__meta">
                  {invite.status === "used" && `Joined: ${invite.used_by_name} on ${dateLabel(invite.used_at)}`}
                  {invite.status === "pending" && `Created ${dateLabel(invite.created_at)}, expires ${dateLabel(invite.expires_at)}`}
                  {invite.status === "expired" && `Expired ${dateLabel(invite.expires_at)}`}
                </span>
              </div>
              {invite.status !== "used" && <button type="button" onClick={() => revoke(invite)}>
                {invite.status === "pending" ? "Revoke" : "Remove"}
              </button>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
