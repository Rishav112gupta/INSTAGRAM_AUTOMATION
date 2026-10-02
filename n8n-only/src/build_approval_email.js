// ============================================================================
// BUILD APPROVAL EMAIL  (Code node, mode: Run Once for All Items)
// For every post the AI just wrote (Status NEEDS_REVIEW), builds an email for
// the approver(s) with the image, caption, hashtags, things to check and
// Approve / Regenerate / Reject buttons.
// Buttons open a confirmation page (workflow 3); nothing changes until the
// person presses "Confirm" there.
// ============================================================================

const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}
const to = (settings['Approver Email'] || '').split(/[,;\s]+/).filter((e) => /.+@.+\..+/.test(e)).join(',');
const base = String($('Config').first().json.approvalLinkUrl || '').trim();
if (!to || !/^https?:\/\//.test(base)) return []; // email approval not set up - approve in the sheet instead

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const company = settings['Company Name'] || 'Instagram';

const out = [];
for (const item of $input.all()) {
  const row = item.json;
  if (String(row['Status'] || '').toUpperCase() !== 'NEEDS_REVIEW' || !row['Approval Code']) continue;

  const link = (action) => `${base}${base.includes('?') ? '&' : '?'}post=${encodeURIComponent(row['Post ID'])}&code=${encodeURIComponent(row['Approval Code'])}&action=${action}`;
  const button = (action, label, color) =>
    `<a href="${link(action)}" style="display:inline-block;padding:12px 22px;margin:4px 6px 4px 0;border-radius:8px;background:${color};color:#ffffff;text-decoration:none;font-weight:bold;font-family:Arial,sans-serif">${label}</a>`;
  const notes = String(row['Review Notes'] || '');
  const hasFlags = notes && !/^No issues found/.test(notes);
  const hashtags = String(row['Hashtags'] || '').split(/\s+/).filter(Boolean).map((t) => '#' + t.replace(/^#/, '')).join(' ');

  const html = `
<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#0f172a">
  <h2 style="margin:0 0 4px">New Instagram post to approve</h2>
  <p style="margin:0 0 16px;color:#475569">${esc(row['Post ID'])} &middot; scheduled for <b>${esc(row['Scheduled Date'])} ${esc(row['Post Time'])}</b> &middot; ${esc(row['Category'] || '')}</p>
  ${row['Image URL'] ? `<img src="${esc(row['Image URL'])}" alt="Post image" style="width:100%;max-width:540px;border-radius:10px;border:1px solid #e2e8f0">` : '<p style="color:#b91c1c"><b>No image yet</b> - choose Regenerate or add an image link in the sheet.</p>'}
  <h3 style="margin:16px 0 6px">${esc(row['Headline'])}</h3>
  <div style="white-space:pre-wrap;line-height:1.5;background:#f8fafc;padding:12px;border-radius:8px">${esc(row['Caption'])}</div>
  <p style="color:#4338ca">${esc(hashtags)}</p>
  <div style="padding:12px;border-radius:8px;margin:12px 0;${hasFlags ? 'background:#fffbeb;border:1px solid #fcd34d' : 'background:#f0fdf4;border:1px solid #86efac'}">
    <b>${hasFlags ? '⚠ Please check before approving:' : 'Checks:'}</b>
    <div style="white-space:pre-wrap;margin-top:6px">${esc(notes || 'No issues found.')}</div>
  </div>
  <div style="margin:18px 0">
    ${button('approve', '✅ Approve', '#16a34a')}
    ${button('regenerate', '🔁 Regenerate', '#4f46e5')}
    ${button('reject', '❌ Reject', '#dc2626')}
  </div>
  <p style="font-size:12px;color:#64748b">Approve = it will be posted automatically at the scheduled time. Regenerate = the AI writes a new version tomorrow morning (you can add notes in the "Review Notes" column first). You can also edit the caption in the Google Sheet before approving. Each button asks you to confirm, and the links work only once.</p>
</div>`;

  out.push({
    json: {
      to,
      subject: `${hasFlags ? '⚠ ' : ''}Approve Instagram post ${row['Post ID']}: ${String(row['Headline'] || row['Topic'] || '').slice(0, 60)} (${company})`,
      html,
    },
  });
}
return out;
