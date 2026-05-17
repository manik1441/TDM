const API = '';
let currentTableName = null;
let currentColumns = [];
let currentRows = [];
let sqlColumns = [];
let sqlRows = [];
let sessionId = null;
let leadAgentMessage = '';
let activeDomainName = 'General Domain';
let activeDomainSlug = '';
let showTablesList = false;
let allTables = [];
let allDomains = [];
let domainSuggestionsMap = {};
let currentTab = 'prompt';

// --- Tabs ---
function switchTab(name) {
  currentTab = name;
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', ['prompt','data','sql'][i]===name));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  
  localStorage.setItem('tdm_active_tab', name);
  
  const oldShow = showTablesList;
  showTablesList = (name === 'data');
  if (name === 'prompt') {
    showTablesList = false;
  }
  if (oldShow !== showTablesList || name === 'data' || name === 'prompt') {
    renderSidebar();
    renderPromptDomainSection();
  }
  if (name !== 'data') {
    closeDataViewerMessage();
  }
}

function goHome() {
  localStorage.setItem('tdm_active_tab', 'prompt');
  window.location.href = '/';
  window.location.reload();
}

// --- Sidebar ---
async function fetchTables() {
  try {
    const r = await fetch(API+'/api/tdm/meta/tables');
    const d = await r.json();
    allTables = d.tables || [];
    renderSidebar();
  } catch(e) { console.error('fetchTables:', e); }
}

async function fetchDomain() {
  try {
    const r = await fetch(API+'/api/tdm/meta/domain');
    const d = await r.json();
    activeDomainName = d.domain || 'General Domain';
    renderSidebar();
    renderPromptDomainSection();
  } catch(e) { console.error('fetchDomain:', e); }
}

function renderSidebar() {
  const section = document.querySelector('.sidebar-section');
  const list = document.getElementById('tableList');
  if (!section || !list) return;
  list.innerHTML = '';

  section.style.display = 'block';
  list.style.display = 'block';

  if (currentTab === 'prompt') {
    section.textContent = 'Existing Domain';
    if (!allDomains.length) {
      const li = document.createElement('li');
      li.className = 'table-item';
      li.textContent = 'No existing domains available';
      li.style.color = 'var(--muted)';
      list.appendChild(li);
      return;
    }

    allDomains.forEach(dom => {
      const li = document.createElement('li');
      li.className = 'table-item' + (dom.slug === activeDomainSlug ? ' active' : '');
      if (dom.slug === activeDomainSlug) {
        li.style.fontWeight = '600';
        li.style.background = 'rgba(99,102,241,0.1)';
        li.style.borderLeft = '3px solid var(--primary)';
      }
      li.textContent = dom.name + (dom.slug === activeDomainSlug ? ' (Active)' : '');
      li.onclick = async () => {
        if (dom.slug === activeDomainSlug) {
          switchTab('data');
        } else {
          await switchDomain(dom.slug);
        }
      };
      list.appendChild(li);
    });
    return;
  }

  if (!showTablesList) {
    section.textContent = 'Active Domain';
    const li = document.createElement('li');
    li.className = 'table-item active';
    li.style.fontWeight = '600';
    li.style.background = 'rgba(99,102,241,0.1)';
    li.style.borderLeft = '3px solid var(--primary)';
    
    li.innerHTML = `${activeDomainName}`;
    li.onclick = () => {
      showTablesList = true;
      switchTab('data');
      renderSidebar();
    };
    list.appendChild(li);
  } else {
    section.textContent = 'Tables';
    
    // const backLi = document.createElement('li');
    // backLi.className = 'table-item';
    // backLi.style.color = 'var(--muted)';
    // backLi.style.fontSize = '0.8rem';
    // backLi.innerHTML = `⬅️ Back to Domain`;
    // backLi.onclick = () => {
    //   showTablesList = false;
    //   renderSidebar();
    // };
    // list.appendChild(backLi);

    allTables.forEach(t => {
      const tableName = typeof t === 'string' ? t : t.name;
      const count = typeof t === 'string' ? null : t.count;
      
      const li = document.createElement('li');
      li.className = 'table-item';
      if (tableName === currentTableName) {
        li.className += ' active';
      }
      
      if (count !== null && count !== undefined) {
        li.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;width:100%">
          <span>${tableName}</span>
          <span class="badge" style="background:rgba(255,255,255,0.08);color:var(--muted);padding:2px 8px;font-size:0.72rem;border-radius:12px;font-weight:600">${count}</span>
        </div>`;
      } else {
        li.textContent = tableName;
      }
      
      li.onclick = () => loadTable(tableName, li);
      list.appendChild(li);
    });
  }
}

async function loadTable(name, el, skipTabSwitch = false) {
  document.querySelectorAll('.table-item').forEach(i => i.classList.remove('active'));
  if(el) el.classList.add('active');
  currentTableName = name;
  if (!skipTabSwitch) {
    switchTab('data');
  }
  document.getElementById('currentTable').textContent = name;
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('dataTable').style.display = 'none';

  const r = await fetch(API+`/api/tdm/meta/table/${name}?limit=10000`);
  const d = await r.json();
  currentColumns = d.columns || [];
  currentRows = d.rows || [];
  
  const total = d.total !== undefined ? d.total : d.rows.length;
  const badgeText = total > d.rows.length ? `Showing ${d.rows.length} of ${total} rows` : `${total} rows`;
  document.getElementById('rowBadge').innerHTML = `<span class="badge">${badgeText}</span>`;
  renderTable('dataHead','dataBody','dataTable', d.columns, d.rows, true);
}

function renderTable(headId, bodyId, tableId, cols, rows, showActions) {
  const thead = document.getElementById(headId);
  const tbody = document.getElementById(bodyId);
  thead.innerHTML = ''; tbody.innerHTML = '';
  if(!cols || !cols.length) return;

  const hr = document.createElement('tr');
  cols.forEach(c => { const th = document.createElement('th'); th.textContent = c; hr.appendChild(th); });
  if(showActions) { const th = document.createElement('th'); th.textContent = ''; hr.appendChild(th); }
  thead.appendChild(hr);

  rows.forEach(row => {
    const tr = document.createElement('tr');
    cols.forEach(c => {
      const td = document.createElement('td');
      td.textContent = row[c] !== null && row[c] !== undefined ? row[c] : 'NULL';
      if(row[c] === null) td.style.color = 'var(--muted)';
      // Inline edit on double click
      td.ondblclick = () => inlineEdit(td, currentTableName, cols[0], row[cols[0]], c, row[c]);
      tr.appendChild(td);
    });
    if(showActions) {
      const td = document.createElement('td');
      td.innerHTML = '<span class="act" title="Delete row">🗑</span>';
      td.querySelector('.act').onclick = () => deleteRow(currentTableName, cols[0], row[cols[0]]);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  });
  document.getElementById(tableId).style.display = 'table';
}

// --- Inline Edit ---
function inlineEdit(td, table, pkCol, pkVal, col, oldVal) {
  const input = document.createElement('input');
  input.value = oldVal !== null ? oldVal : '';
  input.style.cssText = 'background:var(--bg);color:var(--text);border:1px solid var(--primary);border-radius:4px;padding:4px 6px;width:100%;font-size:.85rem';
  td.textContent = '';
  td.appendChild(input);
  input.focus();
  input.onblur = async () => {
    if(input.value !== String(oldVal || '')) {
      const data = {}; data[col] = input.value;
      await fetch(API+`/api/tdm/meta/table/${table}/row?where=${pkCol}=${pkVal}`, {
        method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({data})
      });
    }
    loadTable(table, document.querySelector('.table-item.active'), true);
  };
  input.onkeydown = e => { if(e.key==='Enter') input.blur(); if(e.key==='Escape') loadTable(table, document.querySelector('.table-item.active'), true); };
}

// --- Delete ---
async function deleteRow(table, pkCol, pkVal) {
  if(!confirm('Delete this row?')) return;
  await fetch(API+`/api/tdm/meta/table/${table}/row?where=${pkCol}=${pkVal}`, {method:'DELETE'});
  loadTable(table, document.querySelector('.table-item.active'), true);
  fetchTables();
}

// --- Add Row Modal ---
function addRowModal() {
  if(!currentTableName || !currentColumns.length) return alert('Select a table first');
  document.getElementById('modalTableName').textContent = currentTableName;
  const grid = document.getElementById('modalFields');
  grid.innerHTML = '';
  currentColumns.forEach(c => {
    const div = document.createElement('div');
    div.className = 'form-group';
    div.innerHTML = `<label>${c}</label><input id="modal_${c}" placeholder="${c}">`;
    grid.appendChild(div);
  });
  document.getElementById('addRowOverlay').classList.add('show');
}
function closeModal() { document.getElementById('addRowOverlay').classList.remove('show'); }
async function insertRow() {
  const data = {};
  currentColumns.forEach(c => { const v = document.getElementById('modal_'+c).value; if(v) data[c] = v; });
  await fetch(API+`/api/tdm/meta/table/${currentTableName}/row`, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({data})
  });
  closeModal();
  loadTable(currentTableName, document.querySelector('.table-item.active'), true);
  fetchTables();
}

// --- SQL Console ---
async function runSQL() {
  const q = document.getElementById('sqlInput').value.trim();
  if(!q) return;
  document.getElementById('sqlEmpty').style.display = 'none';
  document.getElementById('sqlTable').style.display = 'none';
  document.getElementById('sqlTopbar').style.display = 'none';
  try {
    const r = await fetch(API+'/api/tdm/meta/query', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q})
    });
    const d = await r.json();
    if(d.error) { document.getElementById('sqlEmpty').textContent = 'Error: '+d.error; document.getElementById('sqlEmpty').style.display='block'; return; }
    sqlColumns = d.columns || [];
    sqlRows = d.rows || [];
    document.getElementById('sqlBadge').textContent = `${sqlRows.length} rows returned`;
    document.getElementById('sqlTopbar').style.display = 'flex';
    renderTable('sqlHead','sqlBody','sqlTable', d.columns, d.rows, false);
  } catch(e) { document.getElementById('sqlEmpty').textContent='Error: '+e.message; document.getElementById('sqlEmpty').style.display='block'; }
}

// --- Premium Custom Dropdown & Download System ---
function toggleDropdown(menuId) {
  event.stopPropagation();
  // Close any other open dropdowns first
  document.querySelectorAll('.dropdown-menu').forEach(m => {
    if (m.id !== menuId) m.classList.remove('show');
  });
  document.getElementById(menuId).classList.toggle('show');
}

// Close dropdowns when clicking outside
window.addEventListener('click', () => {
  document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
});

function triggerDownload(format, source) {
  let columns = [];
  let rows = [];
  let filename = '';
  
  if (source === 'data') {
    if (!currentTableName || !currentColumns.length || !currentRows.length) {
      alert('No data available to download');
      return;
    }
    columns = currentColumns;
    rows = currentRows;
    filename = `${currentTableName}_data.${format}`;
  } else {
    if (!sqlColumns.length || !sqlRows.length) {
      alert('No query results available to download');
      return;
    }
    columns = sqlColumns;
    rows = sqlRows;
    filename = `query_results.${format}`;
  }
  
  const content = generateFormattedContent(format, columns, rows);
  const mimeType = format === 'csv' ? 'text/csv' : format === 'json' ? 'application/json' : 'application/xml';
  
  downloadBlob(content, filename, mimeType);
}

function generateFormattedContent(format, columns, rows) {
  if (format === 'csv') {
    const escapeCsv = val => {
      if (val === null || val === undefined) return '';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };
    
    const headerLine = columns.map(escapeCsv).join(',');
    const rowLines = rows.map(r => columns.map(c => escapeCsv(r[c])).join(','));
    return [headerLine, ...rowLines].join('\n');
  } 
  else if (format === 'json') {
    return JSON.stringify(rows, null, 2);
  } 
  else if (format === 'xml') {
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<records>\n';
    rows.forEach(r => {
      xml += '  <record>\n';
      columns.forEach(c => {
        const tagName = c.replace(/[^a-zA-Z0-9_]/g, '_');
        const val = r[c] !== null && r[c] !== undefined ? String(r[c]) : '';
        const escapedVal = val.replace(/&/g, '&amp;')
                              .replace(/</g, '&lt;')
                              .replace(/>/g, '&gt;')
                              .replace(/"/g, '&quot;')
                              .replace(/'/g, '&apos;');
        xml += `    <${tagName}>${escapedVal}</${tagName}>\n`;
      });
      xml += '  </record>\n';
    });
    xml += '</records>';
    return xml;
  }
  return '';
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], {type: mimeType});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function triggerDownloadAllZip() {
  if (!allTables || !allTables.length) {
    alert('No tables found to download.');
    return;
  }
  
  // Show loading indicator
  const btn = document.querySelector('#dataDownloadDropdown .dropdown-toggle');
  const origText = btn.innerHTML;
  btn.innerHTML = '⚡ Zipping...';
  btn.disabled = true;
  
  try {
    const zip = new JSZip();
    const tableNames = allTables.map(t => typeof t === 'string' ? t : t.name);
    
    for (const tableName of tableNames) {
      const r = await fetch(API+`/api/tdm/meta/table/${tableName}?limit=10000`);
      const d = await r.json();
      
      const cols = d.columns || [];
      const rows = d.rows || [];
      
      if (cols.length > 0) {
        // Generate CSV file content
        const csvContent = generateFormattedContent('csv', cols, rows);
        zip.file(`${tableName}.csv`, csvContent);
        
        // Generate JSON file content
        const jsonContent = generateFormattedContent('json', cols, rows);
        zip.file(`${tableName}.json`, jsonContent);
      }
    }
    
    const zipBlob = await zip.generateAsync({type: 'blob'});
    downloadBlob(zipBlob, `${activeDomainName.toLowerCase().replace(/\s+/g, '_')}_all_tables.zip`, 'application/zip');
  } catch (error) {
    console.error(error);
    alert('Failed to generate ZIP archive: ' + error.message);
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
  }
}

function submitOnEnter(id, handler) {
  document.getElementById(id).addEventListener('keydown', e => {
    if(e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handler();
    }
  });
}

submitOnEnter('sqlInput', runSQL);
submitOnEnter('userPrompt', submitPrompt);

// --- Prompt / Pipeline ---
const PIPELINE_STAGES = [
  {id:'intake', label:'Lead Agent: Intake'},
  {id:'spec_building', label:'Lead Agent: Building Spec'},
  {id:'prompt_building', label:'Prompt Builder: Crafting Prompt'},
  {id:'prompt_review', label:'Review Agent: Checking Prompt'},
  {id:'code_generation', label:'Generator Agent: Producing Code'},
  {id:'code_review', label:'Review Agent: Code Review'},
  {id:'writing_files', label:'Writing Generated Files'},
];

function hidePipeline() {
  const pipeline = document.getElementById('pipelineStatus');
  if(pipeline) pipeline.style.display = 'none';
  const el = document.getElementById('pipelineSteps');
  if(el) el.innerHTML = '';
}

function showPipeline() {
  const pipeline = document.getElementById('pipelineStatus');
  if(!pipeline) return;
  pipeline.style.display = 'block';
  const el = document.getElementById('pipelineSteps');
  el.innerHTML = PIPELINE_STAGES.map(s => `
    <div class="step waiting" id="step-${s.id}">
      <span class="icon">○</span>
      <div class="step-content">
        <span class="step-label">${s.label}</span>
        <span class="step-status">Waiting</span>
      </div>
    </div>
  `).join('');
}

function updateStep(stageId, status, msg) {
  const el = document.getElementById('step-'+stageId);
  if(!el) return;
  el.className = 'step ' + (status==='complete'||status==='revised'?'done':status==='running'?'running':status==='failed'?'failed':'waiting');
  const icons = {done:'✅',running:'⏳',failed:'❌',waiting:'○'};
  el.querySelector('.icon').textContent = icons[el.className.split(' ')[1]] || '○';
  const statusEl = el.querySelector('.step-status');
  if(statusEl) {
    statusEl.textContent = msg || (status==='complete'?'Done':status==='running'?'In progress':status==='failed'?'Failed':'Waiting');
  }
}

function showMessage(text, type) {
  const el = document.getElementById('promptMessage');
  el.style.display = 'block';
  el.style.background = type==='error'?'rgba(239,68,68,.15)':type==='success'?'rgba(34,197,94,.15)':'rgba(99,102,241,.15)';
  el.style.border = '1px solid '+(type==='error'?'var(--red)':type==='success'?'var(--green)':'var(--primary)');
  el.innerHTML = text;
}

function showDataViewerMessage(text, type) {
  const container = document.getElementById('dataViewerMessage');
  const textEl = document.getElementById('dataViewerMessageText');
  if (!container || !textEl) return;
  textEl.innerHTML = text;
  container.style.display = 'flex';
  if (type === 'success') {
    container.style.background = 'rgba(34,197,94,.12)';
    container.style.border = '1px solid rgba(34,197,94,.35)';
    container.style.color = 'var(--green)';
  } else if (type === 'error') {
    container.style.background = 'rgba(239,68,68,.12)';
    container.style.border = '1px solid rgba(239,68,68,.35)';
    container.style.color = 'var(--red)';
  } else {
    container.style.background = 'rgba(99,102,241,.12)';
    container.style.border = '1px solid rgba(99,102,241,.35)';
    container.style.color = 'var(--text)';
  }
}

function closeDataViewerMessage() {
  const container = document.getElementById('dataViewerMessage');
  if (container) container.style.display = 'none';
}

async function submitPrompt() {
  const prompt = document.getElementById('userPrompt').value.trim();
  if(!prompt) return;
  document.getElementById('submitPromptBtn').disabled = true;
  document.getElementById('followupForm').style.display = 'none';
  hidePipeline();
  leadAgentMessage = '';
  showMessage('Analyzing your request...', 'info');

  try {
    const r = await fetch(API+'/api/tdm/generate', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt})
    });
    const d = await r.json();
    sessionId = d.session_id;
    leadAgentMessage = d.result?.message || '';

    if(d.status === 'rejected') {
      showMessage(d.result?.message || 'Request not data-related.', 'error');
      document.getElementById('submitPromptBtn').disabled = false;
      return;
    }

    if(d.needs_followup && d.questions) {
      showMessage('Please fill in the details below, then click Generate Schema.', 'info');
      renderForm(d.questions.questions, d.result?.extracted);
    } else {
      showMessage(leadAgentMessage || 'Requirements understood. Starting generation...', 'info');
      showPipeline();
      updateStep('intake','complete','Requirements understood');
      // Auto-continue with empty structured answers
      runFullPipeline({});
    }
  } catch(e) {
    showMessage('Error: '+e.message, 'error');
  }
  document.getElementById('submitPromptBtn').disabled = false;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  }[ch]));
}

function getQuestionValue(q, extracted) {
  if(q.value !== undefined && q.value !== null) return q.value;
  return extracted && extracted[q.id] ? extracted[q.id] : '';
}

function syncCustomInput(selectEl, customId) {
  const input = document.getElementById(customId);
  if(!input) return;
  const show = selectEl.value === 'Other' || selectEl.value === 'Custom';
  input.style.display = show ? 'block' : 'none';
  input.disabled = !show;
  if(show) input.focus();
}

function getSuggestionsForDomain(domainName) {
  if (!domainName || domainName === 'Other' || domainName === 'Custom') return '';
  const suggestions = domainSuggestionsMap[domainName];
  return Array.isArray(suggestions) ? suggestions.join(', ') : '';
}

function syncDomainAliases(selectEl) {
  const entitiesInput = document.getElementById('fq_entities');
  if (!entitiesInput || !selectEl) return;
  const suggestion = getSuggestionsForDomain(selectEl.value);
  entitiesInput.placeholder = suggestion || 'e.g. Doctors, Patients, Appointments, Prescriptions';
  entitiesInput.value = suggestion || '';
}

function enableFollowupForm() {
  const form = document.getElementById('followupForm');
  if(!form) return;
  form.classList.remove('form-disabled');
  form.querySelectorAll('input, select, textarea, button').forEach(el => el.disabled = false);
}

function disableFollowupForm() {
  const form = document.getElementById('followupForm');
  if(!form) return;
  form.classList.add('form-disabled');
  form.querySelectorAll('input, select, textarea, button').forEach(el => el.disabled = true);
}

function renderForm(questions, extracted) {
  hidePipeline();
  const grid = document.getElementById('formGrid');
  grid.innerHTML = '';
  questions.forEach(q => {
    const div = document.createElement('div');
    div.className = 'form-group' + (q.type==='textarea'?' full':'');
    let html = `<label>${escapeHtml(q.label)}${q.required?' *':''}</label>`;
    const prefill = getQuestionValue(q, extracted);
    if(q.type==='dropdown') {
      const customId = q.custom_id ? `fq_${q.custom_id}` : '';
      html += `<select id="fq_${q.id}"><option value="">— Select —</option>`;
      q.options.forEach(o => html += `<option value="${escapeHtml(o)}" ${o===prefill?'selected':''}>${escapeHtml(o)}</option>`);
      html += '</select>';
      if(q.allow_custom && q.custom_id) {
        const showCustom = prefill === 'Other' || prefill === 'Custom';
        html += `<input id="${customId}" placeholder="${escapeHtml(q.custom_placeholder||'Type value')}" value="${escapeHtml(q.custom_value||'')}" ${showCustom?'':'disabled'} style="display:${showCustom?'block':'none'};margin-top:8px">`;
      }
    } else if(q.type==='textarea') {
      html += `<textarea id="fq_${q.id}" rows="2" placeholder="${escapeHtml(q.placeholder||'')}">${escapeHtml(prefill)}</textarea>`;
    } else {
      html += `<input id="fq_${q.id}" placeholder="${escapeHtml(q.placeholder||'')}" value="${escapeHtml(prefill)}">`;
    }
    div.innerHTML = html;
    grid.appendChild(div);
    if(q.allow_custom && q.custom_id) {
      const select = document.getElementById(`fq_${q.id}`);
      if(select) {
        select.addEventListener('change', () => syncCustomInput(select, `fq_${q.custom_id}`));
        if (q.id === 'domain') {
          select.addEventListener('change', () => syncDomainAliases(select));
        }
      }
    } else if (q.id === 'domain') {
      const select = document.getElementById(`fq_${q.id}`);
      if (select) select.addEventListener('change', () => syncDomainAliases(select));
    }
  });
  const domainSelect = document.getElementById('fq_domain');
  if (domainSelect) syncDomainAliases(domainSelect);
  if (!Object.keys(domainSuggestionsMap).length) {
    fetchDomainAliases();
  }
  enableFollowupForm();
  document.getElementById('followupForm').style.display = 'block';
}

async function submitStructured() {
  if(!sessionId) return;
  const answers = {};
  document.querySelectorAll('#formGrid [id^="fq_"]').forEach(el => {
    if(el.disabled) return;
    const key = el.id.replace('fq_','');
    answers[key] = el.value;
  });
  disableFollowupForm();
  showMessage("Generating schema from your inputs...", 'info');
  showPipeline();
  updateStep('intake','complete','Requirements captured');
  await runFullPipeline(answers);
}

function renderSchemaSummary(schema) {
  const tables = schema.tables || [];
  if (!tables.length) return 'Schema generated, but no tables were discovered yet.';
  const tableHtml = tables.map(table => {
    const safeName = escapeHtml(table.name);
    const columns = (table.columns || []).map(escapeHtml).join(', ');
    return `<div style="margin-top:10px">
      <button class="btn btn-sm btn-outline" onclick="openGeneratedTable('${safeName}')">${safeName}</button>
      <span style="color:var(--muted);font-size:.88rem;margin-left:8px">${columns}</span>
    </div>`;
  }).join('');
  return `<strong>Schema generated for ${escapeHtml(schema.domain || 'active domain')}</strong>
    ${tableHtml}
    <div style="margin-top:14px">
      <button class="btn" onclick="generateDataFromSchema()">Generate Data</button>
      <button class="btn btn-outline" onclick="switchTab('data')">Open Data Viewer</button>
    </div>`;
}

async function fetchSchemaSummary() {
  const r = await fetch(API + '/api/tdm/meta/schema-summary');
  if (!r.ok) throw new Error('Failed to load schema summary');
  return await r.json();
}

async function openGeneratedTable(tableName) {
  switchTab('data');
  await fetchDomain();
  await fetchTables();
  await loadTable(tableName, null, true);
}

async function generateDataFromSchema() {
  showDataViewerMessage('Generating data...', 'info');
  switchTab('data');
  try {
    const r = await fetch(API + '/api/tdm/refresh-data?scale_factor=0.1', {method:'POST'});
    const d = await r.json();
    if (!r.ok || d.detail) {
      showDataViewerMessage(d.detail || 'Data generation failed', 'error');
      return;
    }
    showDataViewerMessage(d.message || 'Data generated.', 'success');
    await fetchDomain();
    await fetchTables();
    const first = allTables[0];
    const firstName = typeof first === 'string' ? first : first?.name;
    if (firstName) await loadTable(firstName, document.querySelector('.table-item'), true);
  } catch(e) {
    showDataViewerMessage('Error: '+e.message, 'error');
  }
}

async function runFullPipeline(answers) {
  updateStep('spec_building','running','Building spec...');
  try {
    const r = await fetch(API+'/api/tdm/generate/structured', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session_id:sessionId, answers})
    });
    const d = await r.json();

    if(d.status==='complete') {
      PIPELINE_STAGES.forEach(s => updateStep(s.id,'complete','Done'));
      const followupForm = document.getElementById('followupForm');
      if(followupForm) followupForm.style.display = 'none';
      await fetchDomains();
      await fetchDomain();
      await fetchTables();
      const schema = await fetchSchemaSummary();
      await fetchTables();
      showMessage(renderSchemaSummary(schema), 'success');
    } else {
      showMessage('Pipeline ended with status: '+(d.status||'unknown')+' — '+(d.error||''), 'error');
      enableFollowupForm();
      // Mark last known stage
      if(d.error) {
        PIPELINE_STAGES.forEach(s => {
          const el = document.getElementById('step-'+s.id);
          if(el && el.className.includes('running')) updateStep(s.id,'failed',d.error);
        });
      }
    }
  } catch(e) {
    showMessage('Pipeline error: '+e.message, 'error');
    enableFollowupForm();
  }
}

// --- Refresh Data ---
function refreshData() {
  openRefreshModal();
}

function openRefreshModal() {
  document.getElementById('refreshScaleFactor').value = '0.1';
  document.getElementById('customScaleGroup').style.display = 'none';
  document.getElementById('refreshOverlay').classList.add('show');
}

function closeRefreshModal() {
  document.getElementById('refreshOverlay').classList.remove('show');
}

function syncRefreshScaleFactor(select) {
  const customGroup = document.getElementById('customScaleGroup');
  if(!customGroup) return;
  const show = select.value === 'custom';
  customGroup.style.display = show ? 'block' : 'none';
  if(show) {
    const input = document.getElementById('customScaleValue');
    if(input) input.focus();
  }
}

async function confirmRefreshData() {
  closeRefreshModal();
  let scale = document.getElementById('refreshScaleFactor').value;
  if (scale === 'custom') {
    scale = parseFloat(document.getElementById('customScaleValue').value) || 0.1;
  }
  showDataViewerMessage('Refreshing and regenerating data...', 'info');
  try {
    const r = await fetch(API+`/api/tdm/refresh-data?scale_factor=${scale}`, {method:'POST'});
    const d = await r.json();
    if (d.message) {
      showDataViewerMessage(d.message, 'success');
      switchTab('data');
    } else {
      showDataViewerMessage(d.detail || 'Done', 'error');
      switchTab('data');
    }
    fetchDomain();
    fetchTables();
    if(currentTableName) loadTable(currentTableName, document.querySelector('.table-item.active'), true);
  } catch(e) { showDataViewerMessage('Error: '+e.message, 'error'); }
}

async function fetchDomains() {
  try {
    const r = await fetch(API+'/api/tdm/meta/domains');
    const d = await r.json();
    allDomains = d.domains || [];
    activeDomainSlug = d.active || '';
    if (activeDomainSlug) {
      const active = allDomains.find(dom => dom.slug === activeDomainSlug);
      if (active) activeDomainName = active.name;
    }
    renderSidebar();
    renderDomainDropdown();
  } catch(e) {
    console.error('Failed to fetch domains:', e);
  }
}

async function fetchDomainAliases() {
  try {
    const r = await fetch(API + '/api/tdm/meta/domain-aliases');
    const d = await r.json();
    domainSuggestionsMap = d.suggested_tables || d.domain_aliases || {};
    const domainSelect = document.getElementById('fq_domain');
    if (domainSelect) syncDomainAliases(domainSelect);
  } catch (e) {
    console.error('Failed to fetch domain aliases:', e);
    domainSuggestionsMap = {};
  }
}

function renderDomainDropdown() {
  const select = document.getElementById('domainSelect');
  if (!select) return;
  select.innerHTML = '';

  if (!allDomains.length) {
    select.innerHTML = '<option value="">No domains available</option>';
    select.disabled = true;
    return;
  }

  select.disabled = false;
  allDomains.forEach(dom => {
    const opt = document.createElement('option');
    opt.value = dom.slug;
    opt.textContent = dom.name;
    if (dom.slug === activeDomainSlug) opt.selected = true;
    select.appendChild(opt);
  });
}

async function switchDomain(slug) {
  if(!slug) return;
  try {
    const r = await fetch(API+'/api/tdm/meta/switch-domain?slug='+encodeURIComponent(slug), {
      method: 'POST'
    });
    const d = await r.json();
    if(d.success) {
      currentTableName = '';
      await fetchDomains();
      await fetchDomain();
      await fetchTables();
      switchTab('data');
    }
  } catch(e) {
    console.error('Failed to switch domain:', e);
  }
}

async function confirmDeleteDomain() {
  const select = document.getElementById('domainSelect');
  if(!select || !select.value) return;
  const slug = select.value;
  const label = select.options[select.selectedIndex]?.textContent || slug;
  if(!window.confirm(`Delete domain '${label}' and all its generated data? This cannot be undone.`)) return;

  try {
    const r = await fetch(API+`/api/tdm/meta/domain/${encodeURIComponent(slug)}`, {
      method: 'DELETE'
    });
    const d = await r.json();
    if(d.success) {
      localStorage.setItem('tdm_active_tab', 'prompt');
      window.location.href = '/';
      window.location.reload();
    } else {
      showDataViewerMessage(d.detail || 'Domain deletion failed', 'error');
    }
  } catch(e) {
    showDataViewerMessage('Error deleting domain: '+e.message, 'error');
  }
}

function renderPromptDomainSection() {
  const section = document.getElementById('existingDomainSection');
  const list = document.getElementById('existingDomainList');
  if (!section || !list) return;

  if (currentTab !== 'prompt' || !allDomains.length) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  list.innerHTML = '';

  allDomains.forEach(dom => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'domain-card' + (dom.slug === activeDomainSlug ? ' active' : '');
    card.innerHTML = `<div class="domain-name">${dom.name}</div>${dom.slug === activeDomainSlug ? '<span class="domain-pill">Active</span>' : ''}`;
    card.onclick = async () => {
      if (dom.slug === activeDomainSlug) {
        switchTab('data');
      } else {
        await switchDomain(dom.slug);
      }
    };
    list.appendChild(card);
  });
}

// --- Init ---
const savedTab = localStorage.getItem('tdm_active_tab') || 'prompt';
switchTab(savedTab);
fetchDomains();
fetchDomainAliases();
fetchDomain();
fetchTables();
