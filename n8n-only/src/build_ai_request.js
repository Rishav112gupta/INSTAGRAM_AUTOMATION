// ============================================================================
// BUILD AI REQUEST  (Code node, mode: Run Once for Each Item)
// Builds the request that asks the AI to write one Instagram post.
// The AI must NOT invent prices, dates, claims etc. - only facts from the
// "Settings" tab (Verified Facts) and the row's "Important Info" may be used.
// ============================================================================

const settings = {};
for (const item of $('Read Settings').all()) {
  const key = String(item.json['Setting'] ?? '').trim();
  if (key) settings[key] = String(item.json['Value'] ?? '').trim();
}
const config = $('Config').first().json;
const row = $json;

const brand = [
  ['Company name', settings['Company Name']],
  ['About the company', settings['Company Description']],
  ['Usual audience', settings['Target Audience']],
  ['Brand voice / tone', settings['Brand Voice']],
  ['Words to avoid', settings['Words To Avoid']],
  ['Hashtags we always like to use', settings['Default Hashtags']],
  ['Content rules', settings['Content Rules']],
]
  .filter(([, v]) => v)
  .map(([k, v]) => `- ${k}: ${v}`)
  .join('\n');

const system = `You are an expert Instagram content writer for a company. Write ORIGINAL, engaging, on-brand posts.

STRICT FACT RULES (these override everything else):
- Never invent prices, fees, discounts, dates, exam dates, deadlines, course details, results, rankings,
  statistics, guarantees, testimonials, names, phone numbers, emails, addresses or links.
- You may only state such a fact if it appears in VERIFIED FACTS or in POST DETAILS below.
- If a fact is needed but missing, leave it out (or write a placeholder like [EXAM DATE]) and list what is
  missing in "missing_information".
- Never promise outcomes ("guaranteed selection", "100% results") unless that exact claim is a verified fact.

Return JSON only:
- headline: max ~8 words, no hashtags
- caption: the Instagram caption WITHOUT hashtags, under 1800 characters, with line breaks, call to action near the end
- hashtags: 8-20 hashtags without the # sign
- image_prompt: a detailed description of an image for an image generator. The image must contain NO text, letters, numbers or logos.
- missing_information: list of facts a human must add or check (empty list if none)`;

const user = `BRAND:
${brand || '- (not filled in yet)'}

VERIFIED FACTS (the only facts you may state):
${settings['Verified Facts'] || '- none - do not state any specific facts, prices or dates'}

POST DETAILS:
- Topic: ${row['Topic'] || ''}
- Category: ${row['Category'] || 'General'}
- Target audience: ${row['Target Audience'] || settings['Target Audience'] || ''}
- Important information: ${row['Important Info'] || '(none)'}
- Call to action: ${row['Call To Action'] || '(choose a suitable one, without inventing offers)'}
- Language: ${settings['Language'] || 'English'}
${row['Status'] === 'REGENERATE' && row['Review Notes'] ? `\nThe previous version was rejected. Reviewer notes: ${row['Review Notes']}` : ''}
Visual style for the image: ${settings['Visual Style'] || 'clean, modern, friendly'}`;

const schema = {
  type: 'object',
  additionalProperties: false,
  required: ['headline', 'caption', 'hashtags', 'image_prompt', 'missing_information'],
  properties: {
    headline: { type: 'string' },
    caption: { type: 'string' },
    hashtags: { type: 'array', items: { type: 'string' } },
    image_prompt: { type: 'string' },
    missing_information: { type: 'array', items: { type: 'string' } },
  },
};

return {
  json: {
    ...row,
    _openai: {
      model: config.textModel,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
      response_format: { type: 'json_schema', json_schema: { name: 'instagram_post', strict: true, schema } },
    },
  },
};
