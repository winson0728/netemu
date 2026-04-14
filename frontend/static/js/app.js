'use strict';

const State = {
  interfaces: [],
  rules: [],
  profiles: [],
  ws: null,
  wsReconnectTimer: null,
  wsPingTimer: null,
};

function ruleByInterface(name) {
  return State.rules.find((item) => item.interface === name) || null;
}

function setWsStatus(status) {
  const el = document.getElementById('ws-status');
  el.className = `ws-status ${status}`;
  el.textContent = status === 'connected' ? 'Realtime Connected' : 'Realtime Offline';
}

function cleanupWsTimers() {
  if (State.wsReconnectTimer) {
    clearTimeout(State.wsReconnectTimer);
    State.wsReconnectTimer = null;
  }
  if (State.wsPingTimer) {
    clearInterval(State.wsPingTimer);
    State.wsPingTimer = null;
  }
}

function scheduleReconnect() {
  if (State.wsReconnectTimer) return;
  State.wsReconnectTimer = setTimeout(() => {
    State.wsReconnectTimer = null;
    connectWS();
  }, 3000);
}

function connectWS() {
  cleanupWsTimers();
  if (State.ws) {
    try {
      State.ws.onclose = null;
      State.ws.onerror = null;
      State.ws.close();
    } catch (_) {}
  }
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  State.ws = new WebSocket(`${protocol}://${location.host}/ws/stats`);

  State.ws.onopen = () => {
    setWsStatus('connected');
    State.wsPingTimer = setInterval(() => {
      if (State.ws && State.ws.readyState === WebSocket.OPEN) {
        State.ws.send('ping');
      }
    }, 15000);
  };

  State.ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleSocketMessage(message);
    } catch (err) {
      console.warn('Failed to parse WebSocket message:', err);
    }
  };

  State.ws.onerror = () => {
    setWsStatus('disconnected');
  };

  State.ws.onclose = () => {
    cleanupWsTimers();
    setWsStatus('disconnected');
    scheduleReconnect();
  };
}

function handleSocketMessage(message) {
  if (message.type === 'stats') {
    const data = message.data || {};
    State.interfaces = State.interfaces.map((iface) => {
      const snap = data[iface.name];
      if (!snap) return iface;
      return {
        ...iface,
        stats: snap.stats,
        qdisc: snap.qdisc,
        rate_rx_bps: snap.stats?.rate_rx_bps || 0,
        rate_tx_bps: snap.stats?.rate_tx_bps || 0,
      };
    });
    renderInterfaces();
    return;
  }
  if (['rule_changed', 'rule_deleted', 'rule_cleared', 'disconnect_changed', 'mode_changed'].includes(message.type)) {
    void refreshData();
  }
}

async function refreshData() {
  try {
    const [interfaces, rules, profiles] = await Promise.allSettled([
      API.interfaces.list(),
      API.rules.list(),
      API.profiles.list(),
    ]);
    if (interfaces.status === 'fulfilled') {
      State.interfaces = interfaces.value;
    } else {
      console.warn('Failed to load interfaces:', interfaces.reason);
    }
    if (rules.status === 'fulfilled') {
      State.rules = rules.value;
    } else {
      console.warn('Failed to load rules:', rules.reason);
    }
    if (profiles.status === 'fulfilled') {
      State.profiles = profiles.value;
    } else {
      console.warn('Failed to load profiles:', profiles.reason);
    }
    populateInterfaceSelects();
    renderInterfaces();
    renderRules();
    renderProfiles();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function populateInterfaceSelects() {
  const options = ['<option value="">Select interface</option>']
    .concat(State.interfaces.map((item) => `<option value="${escapeAttr(item.name)}">${escapeHtml(item.name)} (${escapeHtml(item.state)})</option>`))
    .join('');
  ['rule-iface', 'cfg-downlink-1', 'cfg-uplink-1', 'cfg-downlink-2', 'cfg-uplink-2'].forEach((id) => {
    const el = document.getElementById(id);
    const current = el.value;
    el.innerHTML = options;
    if (current) el.value = current;
  });
}

function renderInterfaces() {
  const root = document.getElementById('iface-grid');
  if (!State.interfaces.length) {
    root.innerHTML = '<div class="empty-state">No interfaces detected.</div>';
    return;
  }
  root.innerHTML = State.interfaces.map((iface) => {
    const rule = ruleByInterface(iface.name);
    const status = rule?.status || 'idle';
    const badges = [];
    if (rule?.bandwidth_kbit) badges.push({ label: `BW ${formatBandwidth(rule.bandwidth_kbit)}` });
    if (rule?.delay_ms) badges.push({ label: `Delay ${rule.delay_ms}ms` });
    if (rule?.loss_pct) badges.push({ label: `Loss ${rule.loss_pct}%`, warn: rule.loss_pct >= 1 });
    if (rule?.variation_enabled) badges.push({ label: 'Variation on' });
    if (rule?.disconnect_schedule?.enabled) badges.push({ label: 'Disconnect cycling', warn: true });
    return `
      <article class="iface-card">
        <header>
          <div>
            <h3>${escapeHtml(iface.name)}</h3>
            <div class="iface-meta">State ${escapeHtml(iface.state)} | Status ${escapeHtml(status)}</div>
          </div>
          <button class="btn btn-ghost" onclick="openRuleEditor('${escapeAttr(iface.name)}')">Edit</button>
        </header>
        <div class="metric-grid">
          <div class="metric"><span class="small">RX</span><strong>${formatRate(iface.rate_rx_bps || 0)}</strong></div>
          <div class="metric"><span class="small">TX</span><strong>${formatRate(iface.rate_tx_bps || 0)}</strong></div>
        </div>
        <div class="rule-badges">${renderBadges(badges)}</div>
        <p class="small">${iface.qdisc ? iface.qdisc : 'No qdisc active'}</p>
      </article>
    `;
  }).join('');
}

function renderRules() {
  const root = document.getElementById('rules-list');
  if (!State.rules.length) {
    root.innerHTML = '<div class="empty-state">No saved rules.</div>';
    return;
  }
  root.innerHTML = State.rules.map((rule) => {
    const badges = [];
    if (rule.bandwidth_kbit) badges.push({ label: `BW ${formatBandwidth(rule.bandwidth_kbit)}` });
    if (rule.delay_ms) badges.push({ label: `Delay ${rule.delay_ms}ms` });
    if (rule.jitter_ms) badges.push({ label: `Jitter ${rule.jitter_ms}ms` });
    if (rule.loss_pct) badges.push({ label: `Loss ${rule.loss_pct}%`, warn: rule.loss_pct >= 1 });
    if (rule.direction) badges.push({ label: rule.direction });
    if (rule.variation_enabled) badges.push({ label: 'Variation enabled' });
    if (rule.disconnect_schedule?.enabled) badges.push({ label: `Disconnect ${rule.disconnect_schedule.disconnect_s}s every ${rule.disconnect_schedule.interval_s}s`, warn: true });
    return `
      <article class="rule-card">
        <header>
          <div>
            <h3>${escapeHtml(rule.label || rule.interface)}</h3>
            <div class="rule-meta">${escapeHtml(rule.interface)} | ${escapeHtml(rule.status)}</div>
          </div>
          <button class="btn btn-ghost" onclick="openRuleEditor('${escapeAttr(rule.interface)}', '${escapeAttr(rule.id)}')">Edit</button>
        </header>
        <div class="rule-badges">${renderBadges(badges)}</div>
        <p class="small">${rule.variation_state?.applied_at ? `Varied at ${new Date(rule.variation_state.applied_at * 1000).toLocaleTimeString()}` : 'Static rule'}</p>
        <div class="actions">
          <button class="btn btn-danger" onclick="toggleDisconnect('${escapeAttr(rule.interface)}', ${rule.status === 'disconnected'})">${rule.status === 'disconnected' ? 'Reconnect' : 'Disconnect'}</button>
          <button class="btn btn-ghost" onclick="clearRule('${escapeAttr(rule.id)}')">Clear</button>
          <button class="btn btn-ghost" onclick="deleteRule('${escapeAttr(rule.id)}')">Delete</button>
        </div>
      </article>
    `;
  }).join('');
}

function renderProfiles() {
  const root = document.getElementById('profiles-list');
  if (!State.profiles.length) {
    root.innerHTML = '<div class="empty-state">No profiles found.</div>';
    return;
  }
  root.innerHTML = State.profiles.map((profile) => `
    <article class="profile-card">
      <h3>${escapeHtml(profile.name)}</h3>
      <div class="profile-meta">${escapeHtml(profile.category)} | ${formatBandwidth(profile.bandwidth_kbit)}</div>
      <p>${escapeHtml(profile.description || 'No description')}</p>
      <div class="profile-badges">
        ${renderBadges([
          profile.delay_ms ? { label: `Delay ${profile.delay_ms}ms` } : null,
          profile.jitter_ms ? { label: `Jitter ${profile.jitter_ms}ms` } : null,
          profile.loss_pct ? { label: `Loss ${profile.loss_pct}%`, warn: profile.loss_pct >= 1 } : null,
        ].filter(Boolean))}
      </div>
      <div class="actions">
        <button class="btn btn-ghost" onclick="applyProfile('${escapeAttr(profile.id)}')">Use Profile</button>
        ${profile.builtin ? '' : `<button class="btn btn-danger" onclick="deleteProfile('${escapeAttr(profile.id)}')">Delete</button>`}
      </div>
    </article>
  `).join('');
}

function openRuleEditor(interfaceName = '', ruleId = '') {
  const overlay = document.getElementById('modal-overlay');
  document.getElementById('modal-title').textContent = ruleId ? 'Edit Rule' : 'Create Rule';
  document.getElementById('rule-id').value = ruleId || '';
  document.getElementById('rule-label').value = '';
  document.getElementById('p-bw').value = 0;
  document.getElementById('p-delay').value = 0;
  document.getElementById('p-jitter').value = 0;
  document.getElementById('p-loss').value = 0;
  document.getElementById('p-corrupt').value = 0;
  document.getElementById('p-duplicate').value = 0;
  document.getElementById('p-disorder').value = 0;
  document.getElementById('p-direction').value = 'egress';
  document.getElementById('var-enabled').checked = false;
  document.getElementById('variation-fields').classList.add('hidden');
  document.getElementById('pv-delay').value = 0;
  document.getElementById('pv-jitter').value = 0;
  document.getElementById('pv-loss').value = 0;
  document.getElementById('pv-bw').value = 0;
  document.getElementById('pv-interval').value = 5;
  document.getElementById('disco-duration').value = 10;
  document.getElementById('disco-enabled').checked = false;
  document.getElementById('disco-schedule-fields').classList.add('hidden');
  document.getElementById('disco-disconnect-s').value = 5;
  document.getElementById('disco-interval-s').value = 30;
  document.getElementById('disco-repeat').value = 0;
  document.getElementById('btn-delete-rule').classList.toggle('hidden', !ruleId);

  if (interfaceName) {
    document.getElementById('rule-iface').value = interfaceName;
  }

  // Auto-find existing rule by interface name if no ruleId given
  if (!ruleId && interfaceName) {
    const existing = State.rules.find((item) => item.interface === interfaceName);
    if (existing) {
      ruleId = existing.id;
      document.getElementById('rule-id').value = ruleId;
      document.getElementById('modal-title').textContent = 'Edit Rule';
      document.getElementById('btn-delete-rule').classList.remove('hidden');
    }
  }

  if (ruleId) {
    const rule = State.rules.find((item) => item.id === ruleId);
    if (rule) {
      document.getElementById('rule-iface').value = rule.interface;
      document.getElementById('rule-label').value = rule.label || '';
      document.getElementById('p-bw').value = rule.bandwidth_kbit || 0;
      document.getElementById('p-delay').value = rule.delay_ms || 0;
      document.getElementById('p-jitter').value = rule.jitter_ms || 0;
      document.getElementById('p-loss').value = rule.loss_pct || 0;
      document.getElementById('p-corrupt').value = rule.corrupt_pct || 0;
      document.getElementById('p-duplicate').value = rule.duplicate_pct || 0;
      document.getElementById('p-disorder').value = rule.disorder_pct || 0;
      document.getElementById('p-direction').value = rule.direction || 'egress';
      if (rule.variation_enabled && rule.variation) {
        document.getElementById('var-enabled').checked = true;
        document.getElementById('variation-fields').classList.remove('hidden');
        document.getElementById('pv-delay').value = rule.variation.delay_range_ms || 0;
        document.getElementById('pv-jitter').value = rule.variation.jitter_range_ms || 0;
        document.getElementById('pv-loss').value = rule.variation.loss_range_pct || 0;
        document.getElementById('pv-bw').value = rule.variation.bw_range_kbit || 0;
        document.getElementById('pv-interval').value = rule.variation.interval_s || 5;
      }
      if (rule.disconnect_schedule && rule.disconnect_schedule.enabled) {
        document.getElementById('disco-enabled').checked = true;
        document.getElementById('disco-schedule-fields').classList.remove('hidden');
        document.getElementById('disco-disconnect-s').value = rule.disconnect_schedule.disconnect_s || 5;
        document.getElementById('disco-interval-s').value = rule.disconnect_schedule.interval_s || 30;
        document.getElementById('disco-repeat').value = rule.disconnect_schedule.repeat || 0;
      }
    }
  }

  overlay.classList.remove('hidden');
}

function closeRuleEditor() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

function collectRuleForm() {
  const variationEnabled = document.getElementById('var-enabled').checked;
  const discoEnabled = document.getElementById('disco-enabled').checked;
  return {
    id: document.getElementById('rule-id').value || undefined,
    interface: document.getElementById('rule-iface').value,
    label: document.getElementById('rule-label').value.trim(),
    bandwidth_kbit: Number(document.getElementById('p-bw').value || 0),
    delay_ms: Number(document.getElementById('p-delay').value || 0),
    jitter_ms: Number(document.getElementById('p-jitter').value || 0),
    loss_pct: Number(document.getElementById('p-loss').value || 0),
    corrupt_pct: Number(document.getElementById('p-corrupt').value || 0),
    duplicate_pct: Number(document.getElementById('p-duplicate').value || 0),
    disorder_pct: Number(document.getElementById('p-disorder').value || 0),
    direction: document.getElementById('p-direction').value,
    variation_enabled: variationEnabled,
    variation: variationEnabled ? {
      delay_range_ms: Number(document.getElementById('pv-delay').value || 0),
      jitter_range_ms: Number(document.getElementById('pv-jitter').value || 0),
      loss_range_pct: Number(document.getElementById('pv-loss').value || 0),
      bw_range_kbit: Number(document.getElementById('pv-bw').value || 0),
      interval_s: Number(document.getElementById('pv-interval').value || 5),
    } : null,
    disconnect_schedule: discoEnabled ? {
      enabled: true,
      disconnect_s: Number(document.getElementById('disco-disconnect-s').value || 5),
      interval_s: Number(document.getElementById('disco-interval-s').value || 30),
      repeat: Number(document.getElementById('disco-repeat').value || 0),
    } : null,
  };
}

async function saveRule() {
  try {
    const payload = collectRuleForm();
    if (!payload.interface) {
      throw new Error('Interface is required');
    }
    const response = await API.rules.save(payload);
    toast(response.tc_result?.success ? 'Rule saved.' : `Rule saved with tc errors: ${(response.tc_result?.errors || []).join(', ')}`, response.tc_result?.success ? 'success' : 'error', 4500);
    closeRuleEditor();
    await refreshData();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function clearRule(ruleId) {
  try {
    await API.rules.clear(ruleId);
    toast('Rule cleared.', 'success');
    await refreshData();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteRule(ruleId) {
  if (!confirm('Delete this rule and remove tc state from the interface?')) return;
  try {
    await API.rules.delete(ruleId);
    toast('Rule deleted.', 'success');
    closeRuleEditor();
    await refreshData();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function toggleDisconnect(interfaceName, disconnected) {
  try {
    await API.rules.disconnect(interfaceName, !disconnected);
    toast(!disconnected ? `${interfaceName} disconnected.` : `${interfaceName} reconnected.`, 'success');
    await refreshData();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function disconnectNow() {
  const iface = document.getElementById('rule-iface').value;
  const rule = ruleByInterface(iface);
  await toggleDisconnect(iface, rule?.status === 'disconnected');
}

async function timedDisconnect() {
  try {
    const iface = document.getElementById('rule-iface').value;
    if (!iface) throw new Error('Interface is required');
    const duration = Number(document.getElementById('disco-duration').value || 10);
    await API.schedule.disconnect(iface, duration);
    toast(`Disconnect scheduled for ${duration}s.`, 'success');
  } catch (error) {
    toast(error.message, 'error');
  }
}

function applyProfile(profileId) {
  const profile = State.profiles.find((item) => item.id === profileId);
  if (!profile) return;
  openRuleEditor();
  document.getElementById('rule-label').value = profile.name;
  document.getElementById('p-bw').value = profile.bandwidth_kbit || 0;
  document.getElementById('p-delay').value = profile.delay_ms || 0;
  document.getElementById('p-jitter').value = profile.jitter_ms || 0;
  document.getElementById('p-loss').value = profile.loss_pct || 0;
  document.getElementById('p-corrupt').value = profile.corrupt_pct || 0;
  document.getElementById('p-duplicate').value = profile.duplicate_pct || 0;
  document.getElementById('p-disorder').value = profile.disorder_pct || 0;
}

async function deleteProfile(profileId) {
  if (!confirm('Delete this custom profile?')) return;
  try {
    await API.profiles.delete(profileId);
    toast('Profile deleted.', 'success');
    await refreshData();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function applyBridge() {
  try {
    const lines = [];
    const dl1 = document.getElementById('cfg-downlink-1').value;
    const ul1 = document.getElementById('cfg-uplink-1').value;
    if (dl1 && ul1) lines.push({ downlink: dl1, uplink: ul1 });
    const dl2 = document.getElementById('cfg-downlink-2').value;
    const ul2 = document.getElementById('cfg-uplink-2').value;
    if (dl2 && ul2) lines.push({ downlink: dl2, uplink: ul2 });
    if (!lines.length) throw new Error('Configure at least one line pair (Downlink + Uplink)');
    const response = await API.rules.setBridge(lines);
    toast(response.success ? `Bridge applied (${lines.length} line${lines.length > 1 ? 's' : ''}).` : `Bridge errors: ${(response.errors || []).join(', ')}`, response.success ? 'success' : 'error', 4500);
  } catch (error) {
    toast(error.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('btn-refresh').addEventListener('click', () => void refreshData());
  document.getElementById('btn-add-rule').addEventListener('click', () => openRuleEditor());
  document.getElementById('btn-close-modal').addEventListener('click', closeRuleEditor);
  document.getElementById('btn-save-rule').addEventListener('click', () => void saveRule());
  document.getElementById('btn-clear-rule').addEventListener('click', () => {
    const ruleId = document.getElementById('rule-id').value;
    if (!ruleId) {
      toast('Save the rule first before clearing it from the modal.', 'info');
      return;
    }
    void clearRule(ruleId);
  });
  document.getElementById('btn-delete-rule').addEventListener('click', () => {
    const ruleId = document.getElementById('rule-id').value;
    if (ruleId) void deleteRule(ruleId);
  });
  document.getElementById('btn-disconnect-now').addEventListener('click', () => void disconnectNow());
  document.getElementById('btn-timed-disconnect').addEventListener('click', () => void timedDisconnect());
  document.getElementById('btn-apply-bridge').addEventListener('click', () => void applyBridge());
  document.getElementById('var-enabled').addEventListener('change', (event) => {
    document.getElementById('variation-fields').classList.toggle('hidden', !event.target.checked);
  });
  document.getElementById('disco-enabled').addEventListener('change', (event) => {
    document.getElementById('disco-schedule-fields').classList.toggle('hidden', !event.target.checked);
  });
  document.getElementById('modal-overlay').addEventListener('click', (event) => {
    if (event.target === event.currentTarget) closeRuleEditor();
  });
  window.openRuleEditor = openRuleEditor;
  window.clearRule = clearRule;
  window.deleteRule = deleteRule;
  window.toggleDisconnect = toggleDisconnect;
  window.applyProfile = applyProfile;
  window.deleteProfile = deleteProfile;

  setWsStatus('disconnected');
  await refreshData();
  connectWS();
});

