# Recovering an accepted request

Implemented 2026-11-12 under stabilization R7. After a reload or lost connection, the signed-in page can show
**Check your last request**. Use **Resume progress** to read the existing request's outcome. This reads the run;
it does not ask the question again, generate another chart, or approve the pack again.

Questions recover their answer and receipts. Charts recover the chart and table. Routes and pack decisions link
to their saved page. An interpreted pack request remains unconfirmed: review it again in the pack before applying
anything. **Dismiss reminder** only clears the reminder; it does not cancel server work.

Only run IDs and page paths are kept in the current tab, scoped to the signed-in employee. Sign-out/account changes
clear them. Nothing is put in localStorage; questions, answers, files and credentials are not saved in browser
storage. Disabled sessionStorage permits in-page observation but cannot preserve the reminder through reload.

Limits: a browser can preserve an ID only after it receives the accepted response. Reloading before that response
arrives requires checking saved history. Runs are process-local and may expire or disappear after an API restart;
the panel then offers the saved page rather than claiming success or resubmitting. A chart or unconfirmed request
that existed only in an expired run cannot be reconstructed from history. Recovery does not make server execution
durable, restore unsent form edits, or transfer reminders between tabs/devices.
