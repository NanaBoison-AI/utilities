# Booking backend — Google Apps Script

`Code.gs` is a Google Apps Script web app that the date site calls when someone
hits **Lock it in**. It:

1. Appends the booking to a Google Sheet (`Timestamp`, `Date`, `Activity`, `User Email`).
2. Emails a confirmation to **both** the owner (`nabbyafua@gmail.com`) and the
   user, using `MailApp`.

## Setup

1. Create (or open) the Google Sheet that should store the bookings.
2. In that sheet: **Extensions → Apps Script**. This creates a script *bound* to
   the spreadsheet (so `SpreadsheetApp.getActiveSpreadsheet()` resolves to it).
3. Replace the default `Code.gs` contents with this folder's `Code.gs`. Save.
4. (Optional) change `OWNER_EMAIL` or `SHEET_NAME` at the top of the file.
5. **Deploy → New deployment → Web app**:
   - **Execute as:** Me
   - **Who has access:** Anyone
6. Authorize when prompted (it needs Sheets + Send email permissions).
7. Copy the **Web app URL** (ends in `/exec`).

## Connect the site

Open `index.html` and set the constant near the top of the `<script>`:

```js
const APPS_SCRIPT_URL = 'https://script.google.com/macros/s/XXXXX/exec';
```

That's it. Submitting the form now writes a row to the sheet and sends the
confirmation emails.

## Notes

- The site POSTs the body as `text/plain` (a JSON string) in `no-cors` mode.
  This avoids a CORS preflight, which Apps Script web apps don't answer. The
  response is opaque to the browser, so the site assumes success once the
  request is sent — check the sheet/inbox to verify delivery.
- Re-deploy (Manage deployments → edit → new version) whenever you change
  `Code.gs`. The `/exec` URL stays the same.
- Visiting the `/exec` URL in a browser hits `doGet` and returns
  `{"ok":true,...}` — a quick way to confirm the deployment is live.
- Gmail accounts have a daily `MailApp` send quota (typically 100/day for
  consumer accounts); fine for this use case.
