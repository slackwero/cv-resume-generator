# Manual testing of the one-click start

CI starts the app from the downloaded ZIP, but it cannot double-click, see a Gatekeeper
prompt or type a password. This checklist covers what only a real machine can show. Each
item has the action and what should happen. If one fails, send the `start.log` from the
app's folder.

Use a machine, or a user account, that has never run the app.

## macOS

- [ ] **Download.** On GitHub, click Code → Download ZIP. In Finder, double-click the ZIP.
  A folder appears with `start.command` inside. Leave it in Downloads.
- [ ] **First double-click.** Note your macOS version (Apple menu → About This Mac).
  Double-click `start.command`. macOS refuses to open it, because it was downloaded.
- [ ] **Open it anyway.** On macOS 14 or earlier: right-click `start.command`, choose
  Open, then Open again. On macOS 15 or later: System Settings → Privacy & Security →
  Open Anyway. A Terminal window opens and the launcher starts. Write down which way worked
  on your macOS version.
- [ ] **Access to Downloads.** macOS asks whether Terminal may access files in your
  Downloads folder. Click Allow: the launcher carries on. If you click Don't Allow instead,
  the window says that CV Generator cannot open its own folder and where to allow it.
- [ ] **The questions.** Without uv, it asks before installing it. Without Homebrew, it
  asks before installing it and then asks for the Mac password (this can take 10 to 20
  minutes). It asks again before installing Pango. Nothing installs without a yes.
- [ ] **Close while starting.** When the window says "Still starting (1 min)...", close
  it. A minute later, port 3000 is free: in a new Terminal window, `lsof -i :3000` prints
  nothing. Double-click `start.command` again to carry on.
- [ ] **The browser opens.** After a few minutes, the browser opens on
  <http://localhost:3000> and shows the Home page.
- [ ] **Import a LinkedIn PDF.** In Sync, upload a profile PDF (More → Save to PDF) and
  apply the changes. The master profile appears in My profile.
- [ ] **Generate a CV.** In New CV, finish the wizard and generate. A PDF appears in
  `output/` and it opens.
- [ ] **Stop.** Close the Terminal window. After a few seconds, <http://localhost:3000>
  no longer answers.
- [ ] **Second start.** Double-click `start.command` again. No questions; the browser
  opens in seconds, and the profile and the CV are still there.
- [ ] **Already running.** With the app running, double-click `start.command` once more.
  It only opens the browser; no second copy starts.
- [ ] **Move the folder.** Stop the app, move the whole folder somewhere else (a path with
  a space, for example) and start it again. It starts, and the data goes with the folder.

## Linux

- [ ] **Start.** Unzip the ZIP, open a terminal in the folder and run `./start.sh`. If it
  says "Permission denied", `bash start.sh` works.
- [ ] **The questions.** It asks before installing curl, unzip and Pango, and uses your
  password through apt or dnf. On another distribution it prints the manual steps instead.
- [ ] **Close while starting.** When it says "Still starting (1 min)...", close the
  terminal window. A minute later, port 3000 is free: in a new terminal,
  `ss -ltn | grep ':3000 '` prints nothing. Run `./start.sh` again to carry on.
- [ ] **The browser opens** on <http://localhost:3000>. Import a PDF and generate a CV as
  above.
- [ ] **Stop.** Press Ctrl+C. The app stops and the port is free.
- [ ] **Second start.** Run `./start.sh` again: seconds, no questions.

## Windows

On Windows, Open uses the PDF's associated viewer. A PDF open in a viewer is locked, so
Regenerate cannot replace it and says to close it and try again.

- [ ] **Download and start.** On GitHub, click Code → Download ZIP, unzip it and
  double-click `start.bat`. Write down whether SmartScreen warns and how you got past it.
- [ ] **The questions.** Without uv or MSYS2 Pango, it asks before installing them
  (uv through Astral's PowerShell installer, MSYS2 through winget, Pango through pacman:
  three separate questions). Nothing installs without a yes.
- [ ] **The browser opens** on <http://localhost:3000> and shows the Home page.
- [ ] **Import the ZIP.** In Sync, upload the LinkedIn ZIP export and apply the changes.
  The master profile appears in My profile.
- [ ] **Import the PDF.** In Sync, upload a profile PDF (More → Save to PDF), review the
  changes and apply them. Nothing you completed by hand is lost.
- [ ] **Contact and photo.** In My profile, edit Contact (the phone, for example) and
  upload a photo. Both are still there after reloading the page.
- [ ] **Wizard and Generate.** In New CV, go through the six steps, check the preview and
  generate. A PDF appears in `output/`.
- [ ] **Open.** Click Open on the CV. The PDF opens in your default viewer.
- [ ] **Regenerate with the PDF open.** Leave the PDF open in the viewer and click
  Regenerate. It does not replace the file and says to close the PDF and try again.
  Close the viewer and click Regenerate again: it works.
- [ ] **Clone and archive.** Clone the CV: a new one appears with the same content.
  Archive one: it leaves the active list and keeps its date and reason.
- [ ] **Stop with Ctrl+C.** Start with `start.bat`, press Ctrl+C in its window. The app
  stops and the port is free: `netstat -ano | findstr :3000` prints nothing.
- [ ] **Stop by closing the window.** Start with `start.bat` and close the window. The
  port is free: `netstat -ano | findstr :3000` prints nothing.
- [ ] **Stop and start again.** Double-click `start.bat` again: seconds,
  no questions, and the profile and the CVs are still there.
