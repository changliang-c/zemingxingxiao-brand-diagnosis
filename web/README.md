# Official research feedback form

`feedback/index.html`, `feedback/form.js` and `assets/research-client-v3.js` are the source for the same-origin intake at <https://www.zmxx.work/feedback/>. Serve these files at those exact paths alongside the engine's `/case-report` route.

The form supports full initial evidence, imported v3 submissions/private receipts, and follow-ups linked to a previous accepted record. It strips supplied identity terms and direct patterns before networking, preserves business measurements, rejects unknown authority or unresolved identity risk, and displays success only after a matching server receipt. It never makes arbitrary prose provably anonymous; the provider must check combinations of clues.

The original WorkBuddy hosted self-check remains a separate platform deployment. Its updated source must be republished through that platform before its new intake behavior can be claimed live.
