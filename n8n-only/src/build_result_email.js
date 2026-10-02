// ============================================================================
// BUILD RESULT EMAIL  (Code node, mode: Run Once for All Items)
// After publishing, emails the approver(s): one email listing what was
// PUBLISHED (with links) and what FAILED or has a PROBLEM (with the reason).
// ============================================================================

const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}
const to = (settings['Approver Email'] || '').split(/[,;\s]+/).filter((e) => /.+@.+\..+/.test(e)).join(',');
if (!to) return [];

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const published = [];
const problems = [];
for (const item of $input.all()) {
  const r = item.json;
  const status = String(r['Status'] || '').toUpperCase();
  if (status === 'PUBLISHED') published.push(r);
  else if (status === 'FAILED' || status === 'PROBLEM') problems.push(r);
}
if (!published.length && !problems.length) return [];

const li = (r, extra) => `<li style="margin-bottom:8px"><b>${esc(r['Post ID'])}</b> - ${esc(r['Headline'] || r['Topic'])}${extra}</li>`;
const html = `<div style="font-family:Arial,sans-serif;max-width:560px;color:#0f172a">
${published.length ? `<h3 style="color:#15803d">🎉 Published on Instagram</h3><ul>${published.map((r) => li(r, r['Instagram URL'] ? ` - <a href="${esc(r['Instagram URL'])}">view post</a>` : '')).join('')}</ul>` : ''}
${problems.length ? `<h3 style="color:#b91c1c">🚨 Needs your attention</h3><ul>${problems.map((r) => li(r, `<br><span style="color:#b91c1c">${esc(r['Status'])}: ${esc(r['Error'])}</span>`)).join('')}</ul><p>Fix the problem in the Google Sheet, then set Status to APPROVED again to retry.</p>` : ''}
</div>`;
const subject = problems.length
  ? `🚨 Instagram: ${problems.length} post(s) need attention${published.length ? `, ${published.length} published` : ''}`
  : `🎉 Instagram: ${published.length} post(s) published`;
return [{ json: { to, subject, html } }];
