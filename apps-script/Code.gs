/**
 * Date-site booking backend (Google Apps Script web app).
 *
 * Responsibilities:
 *   1. Receive a booking POSTed from the site (date, activity, user email).
 *   2. Append a row to the bound Google Sheet.
 *   3. Email a confirmation to BOTH the owner and the user via MailApp.
 *
 * Deploy: see apps-script/README.md. Bind this script to the Spreadsheet that
 * should store the bookings (Extensions > Apps Script from that sheet), then
 * deploy as a Web app with "Execute as: Me" and "Who has access: Anyone".
 */

// The owner who should be notified of every booking.
var OWNER_EMAIL = 'nabbyafua@gmail.com';

// Name of the tab to write to (created automatically if missing).
var SHEET_NAME = 'Bookings';

var HEADERS = ['Timestamp', 'Date', 'Activity', 'User Email'];

/**
 * Web-app entry point for the site's POST request.
 * The body is a JSON string (sent as text/plain to avoid a CORS preflight).
 */
function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonOutput({ ok: false, error: 'No payload received.' });
    }

    var data = JSON.parse(e.postData.contents);
    var date = String(data.date || '').trim();
    var activity = String(data.activity || '').trim();
    var email = String(data.email || '').trim();

    if (!date || !activity || !isValidEmail(email)) {
      return jsonOutput({ ok: false, error: 'Missing or invalid fields.' });
    }

    recordBooking(date, activity, email);
    sendConfirmationEmails(date, activity, email);

    return jsonOutput({ ok: true });
  } catch (err) {
    return jsonOutput({ ok: false, error: String(err) });
  }
}

/** Simple GET so you can sanity-check the deployment in a browser. */
function doGet() {
  return jsonOutput({ ok: true, message: 'Date-site booking API is live.' });
}

/** Append one booking row, creating the sheet + header if needed. */
function recordBooking(date, activity, email) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
  }
  sheet.appendRow([new Date(), date, activity, email]);
}

/** Email both the owner and the user that the date is booked. */
function sendConfirmationEmails(date, activity, email) {
  var pretty = formatDate(date);
  var cleanActivity = activity.replace(/[^\x20-\x7E]+/g, '').trim();
  var subject = "It's a date! 💕 " + pretty;

  var html =
    '<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:auto;' +
    'background:#fff7fb;border:1px solid #ffd0e2;border-radius:16px;padding:24px;color:#4a3b44">' +
    '<h2 style="color:#e23b7d;margin:0 0 12px">It\'s a date! 💗</h2>' +
    '<p style="font-size:16px;margin:6px 0"><b>📆 When:</b> ' + escapeHtml(pretty) + '</p>' +
    '<p style="font-size:16px;margin:6px 0"><b>✨ What:</b> ' + escapeHtml(cleanActivity) + '</p>' +
    '<p style="font-size:15px;margin:16px 0 0;color:#8a6c79">Can\'t wait to see you. 🥹</p>' +
    '</div>';

  // One message addressed to both the owner and the user.
  MailApp.sendEmail({
    to: OWNER_EMAIL + ',' + email,
    subject: subject,
    htmlBody: html,
    name: 'Our Date 💕',
  });
}

/* ---------------- helpers ---------------- */

function isValidEmail(s) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

function formatDate(iso) {
  // iso is YYYY-MM-DD; format as a friendly long date without timezone drift.
  var parts = iso.split('-');
  if (parts.length !== 3) return iso;
  var d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'EEEE, MMMM d, yyyy');
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function jsonOutput(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
