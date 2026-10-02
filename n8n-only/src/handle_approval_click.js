// ============================================================================
// HANDLE APPROVAL CLICK  (Code node, mode: Run Once for All Items)
// Used by workflow 3 (email approval).
//  - Link opened (GET): show a confirmation page with the post and a button.
//    Nothing changes yet - this protects against email scanners that open links.
//  - "Confirm" pressed (POST): check the one-time code, update the Status and
//    clear the code so the email links cannot be used again.
// Output: one item with _html (page to show) and _save (true = update the sheet).
// ============================================================================

// Two webhook nodes share the same address: GET = link opened, POST = Confirm pressed.
const req = $('Confirm pressed').isExecuted ? $('Confirm pressed').first().json : $('Link opened').first().json;
const body = req.body && typeof req.body === 'object' ? req.body : {};
const query = req.query || {};
const confirmed = body.confirm === 'yes';
const input = confirmed ? body : query;
const postId = String(input.post || '').trim();
const code = String(input.code || '').trim();
const action = String(input.action || '').trim().toLowerCase();

const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}
const tz = settings['Timezone'] || 'Asia/Kolkata';

const ACTIONS = {
  approve: { status: 'APPROVED', label: 'Approve', color: '#16a34a', done: 'Approved ✅', after: 'It will be posted automatically at the scheduled time.' },
  regenerate: { status: 'REGENERATE', label: 'Regenerate', color: '#4f46e5', done: 'Sent back to the AI 🔁', after: 'A new version will be written tomorrow morning and emailed to you.' },
  reject: { status: 'REJECTED', label: 'Reject', color: '#dc2626', done: 'Rejected ❌', after: 'This post will not be published.' },
};

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const page = (title, inner) => `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title></head>
<body style="font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:24px"><div style="max-width:520px;margin:auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,.1)">
<h2 style="margin-top:0">${esc(title)}</h2>${inner}</div></body></html>`;
const result = (html, update = null) => [{ json: { _html: html, _save: Boolean(update), ...(update || {}) } }];

const act = ACTIONS[action];
const rowItem = $input.all().find((i) => String(i.json['Post ID'] || '').trim() === postId);
const row = rowItem ? rowItem.json : null;

if (!act || !postId || !code) return result(page('Invalid link', '<p>This link is incomplete. Please use the buttons in the approval email, or change the Status in the Google Sheet.</p>'));
if (!row) return result(page('Post not found', `<p>Post ${esc(postId)} is not in the sheet any more.</p>`));
const status = String(row['Status'] || '').toUpperCase();
if (!row['Approval Code'] || row['Approval Code'] !== code) {
  return result(page('Link already used or expired', `<p>Post <b>${esc(postId)}</b> is currently <b>${esc(status || 'not set')}</b>. Each email link works only once. If you need to change it, edit the Status in the Google Sheet.</p>`));
}
if (status !== 'NEEDS_REVIEW') {
  return result(page('Nothing to do', `<p>Post <b>${esc(postId)}</b> is <b>${esc(status)}</b>, so it can no longer be changed from the email.</p>`));
}

if (!confirmed) {
  const preview = `
${row['Image URL'] ? `<img src="${esc(row['Image URL'])}" alt="" style="width:100%;border-radius:8px">` : ''}
<h3>${esc(row['Headline'])}</h3>
<p style="white-space:pre-wrap;background:#f8fafc;padding:10px;border-radius:8px;max-height:240px;overflow:auto">${esc(row['Caption'])}</p>
<p>Scheduled for <b>${esc(row['Scheduled Date'])} ${esc(row['Post Time'])}</b></p>
<form method="post">
  <input type="hidden" name="post" value="${esc(postId)}"><input type="hidden" name="code" value="${esc(code)}">
  <input type="hidden" name="action" value="${esc(action)}"><input type="hidden" name="confirm" value="yes">
  <button type="submit" style="padding:12px 24px;border:0;border-radius:8px;background:${act.color};color:#fff;font-size:16px;font-weight:bold;cursor:pointer">Confirm: ${esc(act.label)}</button>
</form>`;
  return result(page(`${act.label} post ${postId}?`, preview));
}

const update = {
  row_number: row.row_number,
  Status: act.status,
  'Approval Code': '', // one-time links
  'Last Updated': DateTime.now().setZone(tz).toFormat('yyyy-MM-dd HH:mm'),
};
if (action !== 'approve') update['Review Notes'] = `${String(row['Review Notes'] || '')}\n[${act.status} by email ${update['Last Updated']}]`.trim();
return result(page(act.done, `<p>Post <b>${esc(postId)}</b>: ${esc(act.after)}</p><p style="color:#64748b">You can close this page.</p>`), update);
