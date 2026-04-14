function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/[&"'<>]/g, (ch) => ({ '&': '&amp;', '"': '&quot;', "'": '&#39;', '<': '&lt;', '>': '&gt;' }[ch]));
}

function toast(message, type = 'info', duration = 3000) {
  const container = document.getElementById('toast-container');
  const element = document.createElement('div');
  element.className = `toast ${type}`;
  element.textContent = message;
  container.appendChild(element);
  setTimeout(() => element.remove(), duration);
}

function formatRate(bytesPerSecond) {
  if (bytesPerSecond >= 1_000_000) return `${(bytesPerSecond / 1_000_000).toFixed(2)} MB/s`;
  if (bytesPerSecond >= 1_000) return `${(bytesPerSecond / 1_000).toFixed(1)} KB/s`;
  return `${bytesPerSecond.toFixed(0)} B/s`;
}

function formatBandwidth(kbit) {
  if (!kbit) return 'Unlimited';
  if (kbit >= 1000) return `${(kbit / 1000).toFixed(kbit >= 10000 ? 0 : 1)} Mbps`;
  return `${kbit} kbps`;
}

function renderBadges(items) {
  if (!items.length) return '<span class="badge">Clean link</span>';
  return items.map((item) => `<span class="badge${item.warn ? ' warn' : ''}">${item.label}</span>`).join('');
}
