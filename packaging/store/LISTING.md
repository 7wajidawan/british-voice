# Microsoft Store listing — copy & paste into Partner Center

**App name:** British Voice   _(if taken, try "British Voice for Calls")_

**Category:** Productivity  (sub-category: none)

**Short description (≤ 100 chars):**
Speak normally and be heard in a clear British voice on Zoom, Teams and other calls.

**Description:**
British Voice lets you speak in your normal voice while the people on your call hear a clear,
natural British English voice.

How it works:
• Speak normally into your microphone.
• British Voice recognises your words on your own PC.
• It speaks them in the British voice you chose, through a virtual microphone.
• In Zoom, Teams, Google Meet or any calling app, choose that virtual microphone.

Features:
• 10 British voices (male and female, RP, London, Northern, Scottish), and 100+ more available.
• Each team member can choose a different voice.
• Works offline after the first setup. Your voice never leaves your PC.
• Free, no account, no ads.

Please note:
• The British voice speaks about 1–2 seconds after you finish each sentence.
• It is a synthetic voice that reads out what you said; it is not your own voice.
• Needs the free VB-Cable virtual microphone (the app links to it). Headphones recommended.

**Features (bullet list field):**
- Speak normally, be heard in a British voice
- 10+ distinct British voices for your team
- Works with Zoom, Microsoft Teams, Google Meet
- Runs offline on your PC – private by design

**Search terms:** british accent, accent, voice, uk voice, english accent, calls, meetings

**Privacy policy URL:** link to PRIVACY.md on GitHub (see STORE_GUIDE.md step 5)

**Age rating questionnaire:** no violence, no user-generated content shared, no purchases,
no personal data collected → result should be 3+ / Everyone.

**runFullTrust justification (asked on the Submission options page):**
British Voice is a desktop (Win32) app built with Python. It needs full trust to capture
microphone audio and play generated speech to a user-selected audio output device
(the VB-Cable virtual microphone), which is not possible from a sandboxed app.

**Notes for certification (Submission options → Notes for certification):**
To test without extra software: open the app, click "Preview voice" to hear a British voice.
Then set "Send voice to" = your speakers and click Start; speak into the microphone and the
app repeats your words in a British voice after you pause. First use downloads speech/voice
model files (about 150 MB) from huggingface.co. For use in calling apps, the free third-party
VB-Cable virtual audio driver is optional and linked from the app; it is not bundled.
The app is open source (GPL-3.0); the source code link is in the description.

**Add to the end of the Description:**
Free and open source (GPL-3.0). Source code: <your GitHub repository link>

**Screenshots:** packaging/store/screenshot.png (or take your own of the app window).
**Logo (300×300):** packaging/store/StoreListing300.png
