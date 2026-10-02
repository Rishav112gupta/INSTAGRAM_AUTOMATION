// ============================================================================
// FIND POSTS TO PUBLISH  (Code node, mode: Run Once for All Items)
// Picks rows with Status = APPROVED whose posting time has arrived.
// Only APPROVED rows are ever published (a human must approve first).
// Rows that are approved but not publishable get Status PROBLEM + a reason.
// ============================================================================

const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}
const tz = settings['Timezone'] || 'Asia/Kolkata';
const now = DateTime.now().setZone(tz);

function parseDateTime(dateText, timeText) {
  const date = String(dateText ?? '').trim();
  const time = /^\d{1,2}:\d{2}$/.test(String(timeText ?? '').trim()) ? String(timeText).trim() : '18:00';
  if (!date) return null;
  for (const fmt of ['yyyy-MM-dd H:mm', 'd/M/yyyy H:mm', 'd-M-yyyy H:mm']) {
    const d = DateTime.fromFormat(`${date} ${time}`, fmt, { zone: tz });
    if (d.isValid) return d;
  }
  return null;
}

const output = [];
for (const item of $input.all()) {
  const row = { ...item.json };
  if (String(row['Status'] ?? '').trim().toUpperCase() !== 'APPROVED') continue;
  if (String(row['Instagram Media ID'] ?? '').trim()) continue; // already posted - never post twice

  const when = parseDateTime(row['Scheduled Date'], row['Post Time']);
  const problems = [];
  if (!when) problems.push('Scheduled Date is missing or not in YYYY-MM-DD format.');
  if (!/^https:\/\//.test(String(row['Image URL'] ?? ''))) problems.push('Image URL is empty or not a public https link.');
  const caption = String(row['Caption'] ?? '').trim();
  if (!caption) problems.push('Caption is empty.');
  const tags = String(row['Hashtags'] ?? '').split(/[\s,]+/).map((t) => t.replace(/^#+/, '')).filter(Boolean);
  if (tags.length > 30) problems.push(`Too many hashtags (${tags.length}); Instagram allows 30.`);
  const fullCaption = tags.length ? `${caption}\n\n${tags.map((t) => '#' + t).join(' ')}` : caption;
  if (fullCaption.length > 2200) problems.push(`Caption + hashtags is ${fullCaption.length} characters; Instagram allows 2,200.`);

  if (problems.length) {
    output.push({ json: { ...row, Status: 'PROBLEM', Error: problems.join(' '), _publish: false } });
    continue;
  }
  if (when > now) continue; // not time yet

  output.push({
    json: {
      ...row,
      Status: 'PUBLISHING',
      Error: '',
      'Last Updated': now.toFormat('yyyy-MM-dd HH:mm'),
      _publish: true,
      _caption: fullCaption,
    },
  });
}
return output;
