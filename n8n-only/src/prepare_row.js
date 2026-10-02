// ============================================================================
// PREPARE ROW  (Code node, mode: Run Once for Each Item)
// After the image was generated and uploaded to Cloudinary, builds the final
// Instagram-ready image link (JPEG, 1080x1350 = Instagram's 4:5 portrait size)
// and marks the post NEEDS_REVIEW for a human.
// ============================================================================

const row = $('Check AI text').item.json;
const imageAnswer = $('Create image with AI').item.json;
const upload = $json;
const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}

const notes = String(row['Review Notes'] || '');
const result = { ...row };
delete result._imageRequest;
delete result._ok;
delete result._generate;

function errorText(r) {
  if (!r || !r.error) return '';
  return typeof r.error === 'string' ? r.error : r.error.message || JSON.stringify(r.error);
}

const imageError = errorText(imageAnswer) || (!(imageAnswer.data && imageAnswer.data[0]) ? 'no image returned' : '') || errorText(upload) || (!upload.secure_url ? 'image upload failed' : '');

if (imageError) {
  result['Image URL'] = '';
  result['Review Notes'] = `IMAGE FAILED: ${imageError}. Set Status to REGENERATE to try again, or paste your own public JPEG link in "Image URL".\n` + notes;
} else {
  // Cloudinary transformation: crop to 4:5, 1080x1350, convert to JPEG (Instagram only accepts JPEG).
  const transform = ['c_fill', 'g_auto', 'w_1080', 'h_1350'];
  let overlay = '';
  if (/^(yes|true|y)$/i.test(settings['Headline On Image'] || '') && row['Headline']) {
    // Optional: write the headline on the image (Cloudinary text overlay).
    const text = encodeURIComponent(String(row['Headline']).slice(0, 80)).replace(/%2C/g, '%252C').replace(/%2F/g, '%252F');
    overlay = `/l_text:Arial_64_bold:${text},co_white,b_rgb:00000099,w_960,c_fit/fl_layer_apply,g_south,y_90`;
  }
  const url = String(upload.secure_url).replace('/upload/', `/upload/${transform.join(',')}${overlay}/f_jpg,q_90/`).replace(/\.(png|webp|jpe?g)$/i, '.jpg');
  result['Image URL'] = url;
}

result['Status'] = 'NEEDS_REVIEW';
result['Error'] = '';
result['Last Updated'] = DateTime.now().setZone(settings['Timezone'] || 'Asia/Kolkata').toFormat('yyyy-MM-dd HH:mm');
return { json: result };
