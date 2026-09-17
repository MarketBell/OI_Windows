let state = { rows: [], settings: {} };
let visibleRows = [];
let visibleFullDayRows = [];
const $ = id => document.getElementById(id);
const fmt = value => value == null ? '—' : Number(value).toFixed(2);

function chip(value) {
  if (value == null) return '<span class="chip zero">—</span>';
  const cls = value > 0 ? 'pos' : value < 0 ? 'neg' : 'zero';
  return `<span class="chip ${cls}">${value > 0 ? '+' : ''}${fmt(value)}</span>`;
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok || !data.ok) throw Error(data.error || 'Request failed');
  return data;
}

function setError(error) { $('error').textContent = error?.message || error; $('error').classList.remove('hidden'); }
function clearError() { $('error').classList.add('hidden'); }
function toMinute(time) { const [h, m] = time.split(':').map(Number); return h * 60 + m; }

function filteredRows() {
  const start = toMinute($('startTime').value || '09:15');
  const end = toMinute($('endTime').value || '15:30');
  const frequency = Number($('frequency').value || 3);
  if (end < start) throw Error('End time must be after start time');
  return state.rows.filter(row => {
    const minute = toMinute(row.time);
    return minute >= start && minute <= end && (minute - start) % frequency === 0;
  });
}

function renderTables() {
  try { clearError(); visibleRows = filteredRows(); } catch (error) { setError(error); return; }
  visibleFullDayRows = visibleRows.filter(row => row.ce_day != null && row.pe_day != null);
  $('empty').classList.toggle('hidden', visibleRows.length > 0);
  $('content').classList.toggle('hidden', visibleRows.length === 0);
  if (!visibleRows.length) return;
  const first = visibleRows[0];
  const latest = visibleRows[visibleRows.length - 1];
  const ceTotal = latest.call_oi - first.call_oi;
  const peTotal = latest.put_oi - first.put_oi;
  $('updated').textContent = new Date(latest.captured_at).toLocaleTimeString('en-IN', {hour12:false});
  $('pcr').textContent = fmt(latest.pcr);
  $('bias').textContent = latest.pcr >= 1.1 ? 'Bullish' : latest.pcr <= .8 ? 'Bearish' : 'Neutral';
  $('bias').className = 'chip ' + (latest.pcr >= 1.1 ? 'pos' : latest.pcr <= .8 ? 'neg' : 'zero');
  $('callOi').textContent = fmt(latest.call_oi) + 'L';
  $('putOi').textContent = fmt(latest.put_oi) + 'L';
  $('callDelta').outerHTML = `<i id="callDelta">${chip(ceTotal)}</i>`;
  $('putDelta').outerHTML = `<i id="putDelta">${chip(peTotal)}</i>`;
  $('atm').textContent = latest.atm;
  $('expiryDate').textContent = latest.expiry;
  $('auto').textContent = `${$('frequency').value}M DISPLAY · 1M COLLECTION`;

  $('intradayBody').innerHTML = visibleRows.map((row, index) => {
    const previous = index ? visibleRows[index - 1] : null;
    const ceDiff = previous ? row.call_oi - previous.call_oi : null;
    const peDiff = previous ? row.put_oi - previous.put_oi : null;
    return `<tr class="${index === visibleRows.length - 1 ? 'latest' : ''}"><td>${esc(row.time)}${index === visibleRows.length - 1 ? ' · Latest' : ''}</td><td>${fmt(row.call_oi)}</td><td>${chip(ceDiff)}</td><td>${fmt(row.put_oi)}</td><td>${chip(peDiff)}</td><td><b>${fmt(row.pcr)}</b></td></tr>`;
  }).join('');
  $('intradayFoot').innerHTML = `<tr><td>LATEST − FIRST</td><td colspan="2">${chip(ceTotal)}</td><td colspan="2">${chip(peTotal)}</td><td>${fmt(latest.pcr)}</td></tr>`;

  if (!visibleFullDayRows.length) {
    $('fullDayBody').innerHTML = '<tr><td colspan="5" class="no-data">No full-day readings for this strike filter yet. The next capture will use it.</td></tr>';
    $('fullDayFoot').innerHTML = '';
    return;
  }
  const fullFirst = visibleFullDayRows[0];
  const fullLatest = visibleFullDayRows[visibleFullDayRows.length - 1];
  const fullCeTotal = fullLatest.ce_day - fullFirst.ce_day;
  const fullPeTotal = fullLatest.pe_day - fullFirst.pe_day;
  $('fullDayBody').innerHTML = visibleFullDayRows.map((row, index) => {
    const previous = index ? visibleFullDayRows[index - 1] : null;
    const ceDiff = previous ? row.ce_day - previous.ce_day : null;
    const peDiff = previous ? row.pe_day - previous.pe_day : null;
    return `<tr class="${index === visibleFullDayRows.length - 1 ? 'latest' : ''}"><td>${esc(row.time)}${index === visibleFullDayRows.length - 1 ? ' · Latest' : ''}</td><td>${fmt(row.ce_day)}</td><td>${chip(ceDiff)}</td><td>${fmt(row.pe_day)}</td><td>${chip(peDiff)}</td></tr>`;
  }).join('');
  $('fullDayFoot').innerHTML = `<tr><td>LATEST − FIRST</td><td>${chip(fullCeTotal)}</td><td></td><td>${chip(fullPeTotal)}</td><td></td></tr>`;
}

function render(data) {
  state = data;
  const settings = data.settings;
  $('status').className = 'status online';
  $('status').textContent = settings.zerodha_id ? '● ID saved: ' + settings.zerodha_id : '● Select Zerodha ID';
  $('zerodhaId').innerHTML = '<option value="">Select ID</option>' + data.accounts.map(id => `<option value="${esc(id)}">${esc(id)}</option>`).join('');
  $('zerodhaId').value = settings.zerodha_id || '';
  $('instrument').value = settings.instrument;
  $('expiry').value = settings.expiry_rank;
  $('strikes').value = settings.strike_count;
  $('fullDayStrikes').value = String(settings.full_day_strike_count ?? 0);
  $('titleInstrument').textContent = settings.instrument;
  renderTables();
}

async function load() {
  try { clearError(); render(await api('/api/data')); }
  catch (error) { $('status').className = 'status offline'; $('status').textContent = '● Setup required'; setError(error); }
}

async function saveSettings() {
  try {
    clearError();
    await api('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({zerodha_id:$('zerodhaId').value, instrument:$('instrument').value, expiry_rank:+$('expiry').value, strike_count:+$('strikes').value, full_day_strike_count:+$('fullDayStrikes').value})});
    await load();
  } catch (error) { setError(error); }
}

async function applyFilters() { await saveSettings(); }
async function resetFilters() { $('startTime').value='09:15'; $('endTime').value='15:30'; $('frequency').value='3'; $('fullDayStrikes').value='0'; await saveSettings(); }
async function regenerateToken() { if (!confirm('Generate a fresh token for the saved Zerodha ID?')) return; try { clearError(); $('status').textContent='● Generating token…'; await api('/api/regenerate-token',{method:'POST'}); await load(); } catch(error) { setError(error); $('status').textContent='● Token generation failed'; } }
async function captureNow() { try { clearError(); $('status').textContent='● Checking token…'; await api('/api/capture',{method:'POST'}); await load(); } catch(error) { setError(error); $('status').textContent='● Capture failed'; } }
async function clearToday() { if (!confirm("Clear today's saved readings for this instrument?")) return; try { await api('/api/clear-today',{method:'POST'}); await load(); } catch(error) { setError(error); } }

function downloadCsv() {
  if (!visibleRows.length) return;
  const headers = ['Time','CE OI (L)','CE DF (L)','PE OI (L)','PE DF (L)','PCR','OI-CH-CE (L)','OI-CH-PE (L)'];
  const lines = [headers.join(',')];
  visibleRows.forEach((row,index) => {
    const previous = index ? visibleRows[index-1] : null;
    lines.push([row.time,row.call_oi,previous ? row.call_oi-previous.call_oi : '',row.put_oi,previous ? row.put_oi-previous.put_oi : '',row.pcr??'',row.ce_day,row.pe_day].join(','));
  });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));
  link.download = `${state.settings.instrument}_OI_${new Date().toISOString().slice(0,10)}.csv`;
  link.click(); URL.revokeObjectURL(link.href);
}

load(); setInterval(load,15000);
