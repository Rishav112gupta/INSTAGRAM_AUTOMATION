// ============================================================================
// PLAN POSTS  (Code node, mode: Run Once for All Items)
// Input: rows of the "Posts" tab. Also reads the "Settings" tab.
// 1. Gives every new topic a Post ID and the earliest free posting date
//    on the "every N days" pattern (one post per date).
// 2. Marks rows whose posting date is close enough to be written by AI now,
//    and rows a person set to REGENERATE.
// Output: only rows that changed or must be generated (field _generate).
// ============================================================================

const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}

const tz = settings['Timezone'] || 'Asia/Kolkata';
const everyNDays = Math.max(1, parseInt(settings['Post Every N Days'] || '4', 10) || 4);
const defaultTime = /^\d{1,2}:\d{2}$/.test(settings['Default Post Time'] || '') ? settings['Default Post Time'] : '18:00';
const leadDays = Math.max(0, parseInt(settings['Generate Days Before'] || '3', 10) || 0);
const today = DateTime.now().setZone(tz).startOf('day');

function parseDate(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  let d = DateTime.fromISO(text, { zone: tz });                    // 2026-10-05
  if (!d.isValid) d = DateTime.fromFormat(text, 'd/M/yyyy', { zone: tz }); // 05/10/2026 (day first)
  if (!d.isValid) d = DateTime.fromFormat(text, 'd-M-yyyy', { zone: tz });
  return d.isValid ? d.startOf('day') : null;
}

const startDate = parseDate(settings['Start Date']) || today;

// First date on the "every N days" grid (counted from Start Date) that is >= minDate.
function nextGridDate(minDate) {
  if (minDate <= startDate) return startDate;
  const daysFromStart = Math.floor(minDate.diff(startDate, 'days').days + 1e-9);
  const steps = Math.ceil(daysFromStart / everyNDays);
  let d = startDate.plus({ days: steps * everyNDays });
  if (d < minDate) d = d.plus({ days: everyNDays });
  return d;
}

const rows = $input.all().map((item) => ({ ...item.json }));

// Highest existing Post ID number (P0001, P0002, ...)
let maxId = 0;
for (const row of rows) {
  const m = String(row['Post ID'] ?? '').match(/(\d+)/);
  if (m) maxId = Math.max(maxId, parseInt(m[1], 10));
}

// Dates already taken by a post (one post per date)
const taken = new Set();
for (const row of rows) {
  const d = parseDate(row['Scheduled Date']);
  if (d && String(row['Topic'] ?? '').trim()) taken.add(d.toISODate());
}

// Earliest free date on the "every N days" grid, from today onwards.
function nextFreeDate() {
  let d = nextGridDate(today);
  while (taken.has(d.toISODate())) d = d.plus({ days: everyNDays });
  taken.add(d.toISODate());
  return d;
}

const output = [];
for (const row of rows) {
  const topic = String(row['Topic'] ?? '').trim();
  if (!topic) continue;
  let status = String(row['Status'] ?? '').trim().toUpperCase();
  let changed = false;

  if (status === '' || status === 'NEW') {
    if (!String(row['Post ID'] ?? '').trim()) {
      maxId += 1;
      row['Post ID'] = 'P' + String(maxId).padStart(4, '0');
    }
    let date = parseDate(row['Scheduled Date']);
    if (!date) date = nextFreeDate();
    row['Scheduled Date'] = date.toISODate();
    if (!String(row['Post Time'] ?? '').trim()) row['Post Time'] = defaultTime;
    status = 'PLANNED';
    row['Status'] = status;
    changed = true;
  }

  const date = parseDate(row['Scheduled Date']);
  const dueForWriting = status === 'PLANNED' && date && date.diff(today, 'days').days <= leadDays;
  const generate = status === 'REGENERATE' || Boolean(dueForWriting);

  if (changed || generate) {
    row['Last Updated'] = DateTime.now().setZone(tz).toFormat('yyyy-MM-dd HH:mm');
    output.push({ json: { ...row, _generate: generate } });
  }
}

return output;
