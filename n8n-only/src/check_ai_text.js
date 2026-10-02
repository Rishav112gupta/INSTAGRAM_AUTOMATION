// ============================================================================
// CHECK AI TEXT  (Code node, mode: Run Once for Each Item)
// Reads the AI answer, validates it against Instagram's rules, and flags any
// price / date / percentage / phone / guarantee etc. that is NOT in the
// verified facts or the post's Important Info (so a human checks it).
// Sets _ok = false if the AI call failed (the row is left for a retry tomorrow).
// ============================================================================

const row = $('Build AI request').item.json;
const response = $json;
const config = $('Config').first().json;
const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}

function fail(message) {
  const clean = { ...row };
  delete clean._openai;
  return { json: { ...clean, _ok: false, Error: 'AI writing failed: ' + message } };
}

if (response.error) {
  return fail(typeof response.error === 'string' ? response.error : response.error.message || JSON.stringify(response.error));
}
const message = response.choices && response.choices[0] && response.choices[0].message;
if (!message) return fail('unexpected answer from the AI service');
if (message.refusal) return fail('the AI declined: ' + message.refusal);

let post;
try {
  let text = String(message.content || '').trim();
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) text = fence[1];
  post = JSON.parse(text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1));
} catch (e) {
  return fail('the answer was not valid JSON');
}

const headline = String(post.headline || '').trim().slice(0, 120);
let caption = String(post.caption || '').trim();
const imagePrompt = String(post.image_prompt || '').trim();
if (!headline || !caption || !imagePrompt) return fail('headline, caption or image prompt was empty');

// Hashtags: no #, no spaces, unique, max 30 (Instagram limit)
const seen = new Set();
const hashtags = [];
for (const raw of [...(post.hashtags || []), ...String(settings['Default Hashtags'] || '').split(/[\s,]+/)]) {
  const tag = String(raw).replace(/^#+/, '').replace(/\s+/g, '').trim();
  if (!tag || !/^[\p{L}\p{N}_]+$/u.test(tag) || seen.has(tag.toLowerCase())) continue;
  seen.add(tag.toLowerCase());
  hashtags.push(tag);
}
const tags = hashtags.slice(0, 30);
const hashtagText = tags.map((t) => '#' + t).join(' ');
const maxCaption = 2200 - (hashtagText ? hashtagText.length + 2 : 0);
const notes = [];
if (caption.length > maxCaption) {
  caption = caption.slice(0, maxCaption - 1) + '…';
  notes.push('Caption was shortened to fit Instagram\'s 2,200 character limit.');
}

// ---- Fact guard -----------------------------------------------------------
const sources = [settings['Verified Facts'], settings['Company Name'], settings['Website'], settings['Contact Info'], row['Important Info'], row['Topic'], row['Call To Action']]
  .filter(Boolean)
  .join('\n');
const sourceLower = sources.toLowerCase();
const sourceDigits = sourceLower.replace(/[₹$€£,\s]|rs\.?|inr/g, '');
const months = '(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)';
const checks = [
  ['Price', /(?:₹|rs\.?|inr|\$|usd|€|£)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:rupees|\/-|lakhs?|crores?)/gi],
  ['Percentage', /\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?percent/gi],
  ['Date', new RegExp(`\\b\\d{1,2}(?:st|nd|rd|th)?\\s+${months}\\b(?:,?\\s+\\d{4})?|\\b${months}\\s+\\d{1,2}(?:st|nd|rd|th)?\\b|\\b\\d{1,2}[/-]\\d{1,2}[/-]\\d{2,4}\\b`, 'gi')],
  ['Phone number', /(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){10,12}\b/g],
  ['Email', /[\w.+-]+@[\w-]+\.[\w.-]+/g],
  ['Link', /https?:\/\/\S+|www\.\S+/gi],
  ['Offer / discount', /\b(?:\d+\s?%\s?off|flat\s+\d+|discount|free\s+(?:class|course|trial|demo)|scholarship|offer\s+ends?)\b/gi],
  ['Guarantee / absolute claim', /\b(?:guarantee[ds]?|100\s?%|assured|sure[- ]shot|no\.?\s?1|number\s+one|best\s+in|top\s+ranked)\b/gi],
  ['Numeric claim', /\b\d[\d,]*\+?\s+(?:students|selections|toppers|ranks?|years|learners|results|centres|centers|branches)\b/gi],
  ['Placeholder to fill in', /\[[A-Z][A-Z0-9 _/-]{2,40}\]/g],
];
const flags = [];
const textToCheck = [headline, caption].join('\n').replace(/#\w+/g, '');
for (const [label, re] of checks) {
  for (const m of textToCheck.matchAll(re)) {
    const found = m[0].trim();
    const digits = found.toLowerCase().replace(/[₹$€£,\s]|rs\.?|inr/g, '');
    const verified = label !== 'Placeholder to fill in' && (sourceLower.includes(found.toLowerCase()) || (digits && sourceDigits.includes(digits)));
    if (!verified) flags.push(`${label} "${found}" is not in Verified Facts / Important Info - check it.`);
  }
}
for (const missing of post.missing_information || []) {
  if (String(missing).trim()) flags.push('Missing information: ' + String(missing).trim());
}

const clean = { ...row };
delete clean._openai;
return {
  json: {
    ...clean,
    _ok: true,
    Headline: headline,
    Caption: caption,
    Hashtags: tags.join(' '),
    'Review Notes': [...new Set([...flags, ...notes])].join('\n') || 'No issues found - please still read it before approving.',
    Error: '',
    _imageRequest: {
      model: config.imageModel,
      prompt: `${imagePrompt}\nStyle: ${settings['Visual Style'] || 'clean, modern, friendly'}.\nDo not include any text, letters, numbers or logos in the image.`,
      size: '1024x1536',
      n: 1,
    },
  },
};
