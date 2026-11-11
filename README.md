# OBS settings

Private, credential-free snapshot of OBS Studio settings from the original Windows computer.

Includes global/UI preferences, recording and encoder profiles, audio/video settings,
hotkeys, current scene collections, older scene collection backups, and WebSocket
configuration (server disabled, password removed). Audio filter settings, including
VST filter state, are preserved. The custom text-pulse Lua script and referenced
overlay image are bundled. `manifest.json` lists external dependencies,
bundled assets, and the settings deliberately redacted.

## Restore on another Windows computer

1. Install OBS Studio and Python 3. Start OBS once, then **close OBS**.
2. Clone this private repository:

   ```powershell
   gh repo clone ParthVyas2912/obs-settings
   Set-Location obs-settings
   python .\obs_settings.py restore --dry-run
   python .\obs_settings.py restore
   ```

3. Install required third-party plugins separately: **Move Transition** and
   **Voxengo Marvel GEQ (VST2)**. Plugin binaries are not included.
4. Open OBS and select the desired **Profile** and **Scene Collection**. Reselect
   the camera, microphone, desktop audio device, monitor, and captured windows:
   their IDs depend on the machine. Update recording output folders, missing
   media paths and VST paths. Bundled image/script paths are updated automatically.
5. Sign back into streaming services or re-enter stream keys. Restore browser
   source URLs, custom browser docks, and any network sources manually.
   If using WebSocket, set a **new password** before enabling its server.

The restore command saves copies of files it overwrites in a timestamped sibling
folder next to `%APPDATA%\obs-studio`. Other existing files are left untouched.
Do not restore while OBS is running. Keep the cloned repo until setup is complete.

Only `.json` files are active scene collections. Older `.json.bak` / `.json.v1`
files are retained as history; to recover one, copy it to a new `.json` filename
and import it through OBS's Scene Collection menu.

## Deliberate exclusions

No stream keys, OAuth/access/refresh tokens, account identity fields, WebSocket
passwords, browser cookies/sessions, logs, crash reports, or cache directories
are uploaded. Network URLs are blanked because they can embed credentials;
this includes browser sources and custom ingest servers. Re-enter these locally.
Large recordings and other video media, installers, and
third-party plugin binaries are not bundled. Missing files and dependencies
are recorded in `manifest.json`; this is a settings backup, not an OBS installer.

Review the dependency manifest on the destination machine: some original assets
may already be missing on the source computer. Hardware-specific encoders also
require compatible hardware/drivers, or selection of another encoder.

## Check or refresh the backup

```powershell
python .\obs_settings.py validate
```

For a fresh snapshot, use a separate empty directory containing `obs_settings.py`
and run `python .\obs_settings.py snapshot`. It intentionally refuses to overwrite
an existing snapshot. Never copy raw OBS account/browser configuration into Git.
