// ============================================================================
// PUBLISH RESULT  (Code node, mode: Run Once for Each Item)
// Looks at the answers of the Instagram steps and writes the outcome:
// PUBLISHED (with the Instagram link) or FAILED (with a clear reason).
// A FAILED post is never retried automatically - set Status back to APPROVED
// to try again. This guarantees nothing is posted twice by accident.
// ============================================================================

const row = $('Find posts to publish').item.json;
const container = $('Create Instagram container').item.json;
const status = $('Check container').item.json;
const published = $('Publish to Instagram').item.json;
const media = $json;
const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}

function errorOf(r) {
  if (!r || !r.error) return null;
  const e = r.error;
  if (typeof e === 'string') return { message: e };
  return { message: e.error_user_msg || e.message || JSON.stringify(e), code: e.code };
}

const result = { ...row };
delete result._publish;
delete result._caption;
result['Last Updated'] = DateTime.now().setZone(settings['Timezone'] || 'Asia/Kolkata').toFormat('yyyy-MM-dd HH:mm');
if (container && container.id) result['Container ID'] = String(container.id);

if (published && published.id) {
  result['Status'] = 'PUBLISHED';
  result['Instagram Media ID'] = String(published.id);
  result['Instagram URL'] = (media && media.permalink) || '';
  result['Error'] = '';
  return { json: result };
}

const err = errorOf(container) || errorOf(status) || errorOf(published) || { message: 'Unknown problem - no media id was returned.' };
let hint = '';
if (err.code === 190) hint = ' The Instagram access token is invalid or expired: create a new token and update the "Instagram access token" credential in n8n (see guide).';
else if (status && status.status_code && status.status_code !== 'FINISHED') hint = ` Instagram had not finished processing the image (status ${status.status_code}). Set Status back to APPROVED to try again.`;
else if (/media|image|url|download/i.test(err.message)) hint = ' Check that "Image URL" opens a JPEG image in a private browser window.';

result['Status'] = 'FAILED';
result['Error'] = `Instagram: ${err.message}.${hint} Nothing was posted. To retry, set Status to APPROVED.`;
return { json: result };
