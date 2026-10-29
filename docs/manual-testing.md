# Manual testing of the one-click start

CI starts the app from the downloaded ZIP, but it cannot double-click, see a Gatekeeper
prompt or type a password. This checklist covers what only a real machine can show. Each
item has the action and what should happen. If one fails, send the `start.log` from the
app's folder.

Use a machine, or a user account, that has never run the app.

## macOS

- [ ] **Download.** On GitHub, click Code → Download ZIP. In Finder, double-click the ZIP.
  A folder appears with `start.command` inside.
- [ ] **First double-click.** Double-click `start.command`. macOS refuses to open it,
  because it was downloaded.
- [ ] **Right-click → Open.** Right-click `start.command`, choose Open, then Open again.
  A Terminal window opens and the launcher starts.
- [ ] **The questions.** Without uv, it asks before installing it. Without Homebrew, it
  asks before installing it and then asks for the Mac password (this can take 10 to 20
  minutes). It asks again before installing Pango. Nothing installs without a yes.
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
- [ ] **The browser opens** on <http://localhost:3000>. Import a PDF and generate a CV as
  above.
- [ ] **Stop.** Press Ctrl+C. The app stops and the port is free.
- [ ] **Second start.** Run `./start.sh` again: seconds, no questions.

Windows is added with the next part of the launcher.
