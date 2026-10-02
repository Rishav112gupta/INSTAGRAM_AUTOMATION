# Instagram automation with n8n only (no coding, no server)

This folder lets you run the Instagram automation **entirely inside n8n**: no Docker, no dashboard, no code. Your team works in a **Google Sheet**; n8n does the rest.

```
 Google Sheet (your team)            n8n (runs by itself)                      Services
 ──────────────────────             ─────────────────────                     ─────────
 1. Add a topic           ──►  Workflow 1, every day 08:00:
                                • gives it a date (every 4th day)
                                • 3 days before: AI writes caption      ──►  OpenAI
                                  + hashtags + creates image            ──►  Cloudinary (hosts the image)
 2. Status = NEEDS_REVIEW  ◄──  • fills the row, flags anything to check
                                • emails you the post                   ──►  Gmail
 3. You click APPROVE in the   ──►  Workflow 3 sets Status = APPROVED
    email (or set APPROVED
    in the sheet)          ──►  Workflow 2, every 15 minutes:
                                • at the date/time, posts it            ──►  Instagram (official API)
 4. Status = PUBLISHED     ◄──  • writes the Instagram link back
```

**Nothing is ever posted unless a person approves it**, either with the button in the approval email or by setting the row to APPROVED in the sheet.

Files in this folder:

| File | What it is |
|---|---|
| `template/instagram-posts-template.xlsx` | The Google Sheet template (tabs: Posts, Settings, How to use) |
| `workflows/1-plan-and-write-posts.json` | n8n workflow 1: plans dates and writes posts with AI |
| `workflows/2-publish-approved-posts.json` | n8n workflow 2: publishes approved posts to Instagram and emails you the result |
| `workflows/3-email-approval.json` | n8n workflow 3: makes the Approve / Regenerate / Reject buttons in the email work |

---

## What you need (accounts)

| Account | Why | Cost |
|---|---|---|
| **n8n Cloud**: <https://n8n.io> | Runs the workflows 24/7 | Paid plan after the free trial |
| **Google account** | The Google Sheet, and Gmail for the approval emails | Free |
| **OpenAI**: <https://platform.openai.com> | AI text and images | Pay per use (add a payment method) |
| **Cloudinary**: <https://cloudinary.com> | Hosts the images so Instagram can download them | Free plan is enough to start |
| **Instagram Professional account** + **Meta developer account**: <https://developers.facebook.com> | Official permission to post | Free |

Check each provider's website for current prices.

> **Why n8n Cloud?** It is always on, so posts go out on time even when your computer is off. You can also run n8n on your own computer (see the end of this guide), but it only works while that computer is on.

---

## Step 1: Create the Google Sheet (5 min)

1. Download `template/instagram-posts-template.xlsx` from this GitHub repository (click the file → **Download raw file**).
2. Go to <https://drive.google.com> → **New → File upload** → choose the file.
3. Double-click it in Drive. It opens in Google Sheets. Click **File → Save as Google Sheets**. **This matters:** n8n can only use a real Google Sheet, not an .xlsx file.
4. In the new Google Sheet, open the **Settings** tab and fill in your company details:
   - **Verified Facts**: real prices, dates, addresses and phone numbers, one per line. The AI may only use facts from here or from a row's "Important Info"; anything else gets flagged for you.
   - **Post Every N Days** = `4` and **Start Date** = your first posting date (format `2026-10-05`).
   - **Default Post Time** = e.g. `18:00`. **Timezone** = `Asia/Kolkata`.
   - **Approver Email** = the email address that should receive posts to approve, e.g. `boss@yourcompany.com`. For several people, separate them with commas. Leave it empty if you prefer to approve only in the sheet.
5. Copy the sheet's link from the browser address bar. You'll need it in Step 6.

Don't rename the tabs (`Posts`, `Settings`) or the column headers.

## Step 2: Cloudinary (5 min)

1. Sign up at <https://cloudinary.com>.
2. On the Dashboard, copy your **Cloud name**.
3. Go to **Settings (gear) → Upload → Upload presets → Add upload preset**. Set **Signing mode** to **Unsigned**, then **Save**. Copy the preset **name**.

## Step 3: OpenAI key (5 min)

1. Go to <https://platform.openai.com> → **Settings → Billing** and add a payment method.
2. Go to **API keys → Create new secret key**, and copy it. Keep it private; you'll paste it only into n8n.

## Step 4: Instagram permission (20-30 min)

1. In the Instagram app: **Settings → Account type and tools → Switch to professional account** (Business or Creator).
2. Go to <https://developers.facebook.com>, then **My Apps → Create App**. Choose the Instagram use case ("Manage messaging & content on Instagram") and the **Business** app type.
3. In the app: **Instagram → API setup with Instagram login**.
4. Under **Generate access tokens**, click **Add account** and log in with your Instagram account. If asked to accept a tester invitation, do so in Instagram → Settings → Apps and websites.
5. Copy two things:
   - the **Instagram account ID** (a long number shown next to your account)
   - the **access token** (click **Generate token**)

   The token is valid for **60 days**. Put a reminder in your calendar for day 50 (see "Renewing the Instagram token" below).

## Step 5: n8n credentials (10 min)

In n8n: **Overview → Credentials → Create credential** (or the **+** button). Create four:

| Search for | Name it exactly | Fill in |
|---|---|---|
| **Google Sheets OAuth2 API** | `Google Sheets account` | Click **Sign in with Google** and allow access |
| **OpenAI** | `OpenAI account` | Paste your OpenAI API key |
| **Query Auth** | `Instagram access token` | **Name:** `access_token` · **Value:** your Instagram token |
| **Gmail OAuth2 API** | `Gmail account` | Click **Sign in with Google** and allow access. The emails are sent **from** this Gmail account. |

On n8n Cloud, "Sign in with Google" works straight away. (On a self-hosted n8n, Google sign-in first needs a Google Cloud "OAuth client"; n8n's credential screen links to the instructions.)

## Step 6: Import the three workflows (15 min)

Do this for **each** file in `workflows/` (download them from GitHub first):

1. In n8n: **Create workflow**, then use the **⋯** menu (top right) → **Import from File** and choose the file.
2. Double-click the **Config** node and fill in the fields:
   - Workflow 1: `sheetUrl` (your sheet link), `cloudinaryCloudName`, `cloudinaryUploadPreset`. The models can stay as they are; change them only if OpenAI has retired them.
   - Workflow 2: `sheetUrl` and `instagramAccountId`.
   - Workflow 3: `sheetUrl`.
3. Open every node with a ⚠️ warning (the Google Sheets, OpenAI, Instagram and Gmail nodes) and pick the credential you created in Step 5.
4. Click **Save**.

Then connect the email buttons (once):

1. In **workflow 3**, turn on the **Active** / **Publish** switch at the top. The buttons only work while it is on.
2. Double-click the **Link opened** node. Click **Production URL** and copy the address. It looks like `https://yourname.app.n8n.cloud/webhook/instagram-approval`. (Not the *Test URL*.)
3. In **workflow 1**, open **Config** and paste it into **approvalLinkUrl**. Click **Save**.

## Step 7: Test it (10 min)

1. In the sheet's **Posts** tab there are 3 example topics. In **Settings**, set **Start Date** to **today's date**.
2. Open workflow **1. Plan & write posts** → click **Test workflow** (or **Execute workflow**). Wait about 1-2 minutes.
3. Look at the sheet. The rows now have a Post ID and a date. The first one is **NEEDS_REVIEW**, with a Headline, Caption, Hashtags and an Image URL (open it to see the image).
4. Read the **Review Notes**. They list anything the AI wrote that isn't in your Verified Facts (prices, dates, "guaranteed", …). Fix the caption if needed.
5. Check your inbox (and the spam folder the first time). There is an email **"Approve Instagram post P0001 …"** with the image, caption, hashtags and the things to check. A ⚠ at the start of the subject means something was flagged.
6. To try publishing right now: set that row's **Post Time** to a time a few minutes ago. Then click **✅ Approve** in the email, and **Confirm: Approve** on the page that opens. The row's Status becomes **APPROVED**. (Or simply type APPROVED in the sheet.)
7. Open workflow **2. Publish approved posts** → **Test workflow**. After about 1 minute the row says **PUBLISHED**, with a link in **Instagram URL**. That's a real Instagram post. You also get an email "🎉 Instagram: 1 post(s) published".

## Step 8: Switch it on

In each of the three workflows, turn on the **Active** / **Publish** switch (top of the screen).

- Workflow 1 now runs every day at 08:00, keeps your schedule filled, and emails you each new post.
- Workflow 2 checks every 15 minutes for approved posts that are due, and emails you what was published or what failed.
- Workflow 3 waits for clicks on the email buttons.

---

## Your daily routine (2 minutes)

1. **Add topics** as new rows in **Posts**. Only **Topic** is needed; **Important Info** is where real facts go (dates, fees, batch names).
2. **Review the email** ("Approve Instagram post …"). Look at the image, read the caption and the yellow "Please check" box. Then click a button:
   - **✅ Approve**: it will be posted at its date and time.
   - **🔁 Regenerate**: the AI writes it again tomorrow morning, and you get a new email. To tell the AI what to change, write it in the row's **Review Notes** first.
   - **❌ Reject**: dropped.

   A page opens and asks you to **Confirm**. Nothing changes until you press it. Each email's buttons work **once**; after that, change the Status in the sheet.

   **Want to fix a word before approving?** Edit the **Caption** in the sheet, then click Approve in the email. The sheet is what gets posted.
3. **Or decide in the sheet** (always works, with or without email): filter **Status = NEEDS_REVIEW** and set **Status** to:
   - **APPROVED**: it will be posted at its date and time.
   - **REGENERATE**: the AI writes it again tomorrow morning. Write what to change in **Review Notes** first.
   - **REJECTED**: dropped.
4. **Check** the result emails, or the sheet: **PUBLISHED** rows have the Instagram link. **FAILED** or **PROBLEM** rows explain what's wrong in **Error**. Fix it and set **APPROVED** again.

You can change any **Scheduled Date** (format `2026-10-05`) or **Post Time** (format `18:00`) by hand at any time.

## Renewing the Instagram token (every ~50 days)

Repeat Step 4.4-4.5 (Generate token), then in n8n open **Credentials → Instagram access token** and paste the new value. If you forget, posts will show **FAILED** with the message "access token is invalid or expired". Renew the token and set them back to **APPROVED**.

## Troubleshooting

| You see | Do this |
|---|---|
| Workflow error: "The resource you are requesting could not be found" (Google) | The `sheetUrl` is wrong, or the file is still an .xlsx. Use **File → Save as Google Sheets** (Step 1.3). |
| Error mentions a column name | Don't rename the headers. Copy them again from the template. |
| `AI writing failed: Incorrect API key` | Fix the OpenAI credential. |
| `AI writing failed: … model …` | Change `textModel` / `imageModel` in Config to a model listed at platform.openai.com/docs/models. |
| Review Notes start with `IMAGE FAILED` | Check the Cloudinary cloud name and that the preset is **Unsigned**. Set Status to **REGENERATE** to retry, or paste your own public **https** JPEG link into **Image URL**. |
| `FAILED … access token` | Renew the Instagram token (above). |
| `FAILED … Image URL` / `container status ERROR` | Open the Image URL in a private browser window; it must show the image. |
| `PROBLEM` | Read **Error**: usually a missing image, an empty caption, or a date not in `YYYY-MM-DD` format. |
| Nothing happens | Are all three workflows **Active**? Is Status exactly `APPROVED`? Is the date/time in the past? |
| No approval email | Is **Approver Email** filled in (Settings tab)? Is `approvalLinkUrl` in workflow 1's Config the Production URL (starting with `https://`)? Look in spam. In n8n **Executions**, open the last run of workflow 1 and check the **Send approval email** step. |
| Email button shows "This page isn't working" / 404 | Workflow 3 is not **Active**, or `approvalLinkUrl` is the *Test URL* instead of the *Production URL*. |
| Email button says "Link already used or expired" | That email's buttons were already used, or a newer version was written (Regenerate). Use the newest email, or change the Status in the sheet. If it happens for **every** new email, the **Approval Code** column is missing: add it (see "Already using the sheet from before?" below). |
| Email button says "Post not found" | The row was deleted, or its Post ID was changed. |

In n8n, **Executions** (left menu) shows every run, and clicking one shows exactly which step failed.

## Already using the sheet from before?

If you set up the sheet before email approval existed, add two things by hand:

1. **Posts** tab: in the first empty column after **Last Updated**, type the header `Approval Code`.
2. **Settings** tab: add a row with `Approver Email` in the **Setting** column and your email address in **Value**.

Then re-import the three workflows (Step 6). Your rows are not affected.

## Good to know

- **Email button safety:** every post gets a new random code, and the buttons only work with it, so nobody can approve by guessing a link. The code is deleted after one use. Opening a link only shows a page; the change happens when a person presses **Confirm**, so email virus scanners that "click" links can't approve anything. Still, anyone you **forward** an approval email to can use its buttons, so don't forward them.
- **Safety:** only APPROVED rows are posted. A row is set to PUBLISHING before posting, and FAILED posts are never retried automatically, so nothing gets posted twice by accident.
- **Instagram rules handled for you:** images are converted to JPEG at 1080×1350 (4:5 portrait), captions are capped at 2,200 characters and hashtags at 30. Instagram allows 100 API posts per day.
- **Headline on the image:** set **Headline On Image** = `Yes` in Settings to print the headline on the picture (Cloudinary text overlay). Check the first few images when you turn it on.
- **Running n8n on your own computer instead of the cloud:** install Docker Desktop and run `docker run -it --rm -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n`, then open <http://localhost:5678>. Posting works because the images are on Cloudinary, but only while your computer is on.
- **Want more?** The full app in the rest of this repository adds a web dashboard, calendar, user roles and more. See the main [README](../README.md).

## For developers

- The JavaScript inside the Code nodes lives in `src/`. Rebuild the workflow files with `python3 build_workflows.py`.
- `python3 tests/run_tests.py` (needs Docker) runs all three workflows inside a real n8n 2.41.6, with fake OpenAI, Cloudinary and Instagram services and sample sheet rows. Gmail nodes are replaced by pass-through steps, so no email is sent; the tests check the email content instead. It checks planning, AI checks, image links, approval emails and codes, the approval web pages (open, confirm, used code, regenerate), publishing, failures, result emails and no-double-posting.
- Regenerate the sheet template with `python3 template/make_template.py` (needs `openpyxl`).
