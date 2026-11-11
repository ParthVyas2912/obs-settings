"""Create a credential-free OBS snapshot, or restore it on another computer."""

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "config"
SECRET = re.compile(
    r"password|passwd|secret|token|authorization|credential|cookie|streamkey|apikey",
    re.IGNORECASE,
)
NETWORK = re.compile(r"(?:https?|wss?|rtmps?|rtsp|srt)://", re.IGNORECASE)


def sensitive(key):
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return bool(SECRET.search(normalized)) or normalized in {
        "key", "auth", "username", "login", "channelname",
    }


def clean(value, removed, trail=""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            location = f"{trail}/{key}"
            if sensitive(key):
                result[key] = ""
                if item:
                    removed.append(location)
            else:
                result[key] = clean(item, removed, location)
        return result
    if isinstance(value, list):
        return [clean(item, removed, f"{trail}/{index}")
                for index, item in enumerate(value)]
    if isinstance(value, str) and NETWORK.search(value):
        removed.append(trail)
        return "about:blank"
    return value


def read_ini(path):
    data = configparser.RawConfigParser(strict=False)
    data.optionxform = str
    data.read(path, encoding="utf-8-sig")
    return data


def write_ini(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        data.write(handle, space_around_delimiters=False)


def write_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n",
                    encoding="utf-8")


def references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and re.match(r"^[A-Za-z]:[\\/]", item):
                yield key, item
            yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def snapshot(source):
    if SNAPSHOT.exists() or (ROOT / "manifest.json").exists():
        raise SystemExit("Snapshot already exists; use a new checkout for a new snapshot.")
    if not (source / "global.ini").is_file():
        raise SystemExit(f"OBS configuration not found: {source}")
    removed = []
    dependencies = {}
    files = [source / name for name in ("global.ini", "user.ini")
             if (source / name).is_file()]
    files += sorted((source / "basic").rglob("*"))
    websocket = source / "plugin_config" / "obs-websocket" / "config.json"
    modules = source / "plugin_manager" / "modules.json"
    files += [file for file in (websocket, modules) if file.is_file()]
    for file in files:
        if not file.is_file():
            continue
        relative = file.relative_to(source)
        if file.suffix == ".ini":
            data = read_ini(file)
            for section in list(data.sections()):
                if re.search(r"youtube|twitch|auth|facebook", section, re.I):
                    data.remove_section(section)
                    removed.append(f"{relative}/{section}")
                    continue
                for key, value in list(data[section].items()):
                    if sensitive(key) or key.lower() == "installguid":
                        data.set(section, key, "")
                        if value:
                            removed.append(f"{relative}/{section}/{key}")
                    elif key.lower() == "extrabrowserdocks":
                        data.set(section, key, "[]")
                        removed.append(f"{relative}/{section}/{key}")
                    elif key.lower() == "serverenabled":
                        data.set(section, key, "false")
                    elif NETWORK.search(value):
                        data.set(section, key, "")
                        removed.append(f"{relative}/{section}/{key}")
            write_ini(data, SNAPSHOT / relative)
        elif ".json" in file.name:
            data = json.loads(file.read_text(encoding="utf-8-sig"))
            for key, value in references(data):
                dependencies[value] = {
                    "setting": key,
                    "exists_on_original_machine": Path(value).is_file(),
                    "included": False,
                }
            data = clean(data, removed, str(relative))
            if file == websocket:
                for key in list(data):
                    if re.sub(r"[^a-z]", "", key.lower()) == "serverenabled":
                        data[key] = False
            write_json(data, SNAPSHOT / relative)
        else:
            raise SystemExit(f"Unrecognized settings file; inspect before uploading: {relative}")
    assets = []
    for original, info in dependencies.items():
        file = Path(original)
        if info["setting"] in ("file", "local_file", "path") and file.is_file():
            if file.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".lua"}:
                if file.stat().st_size <= 20 * 1024 * 1024:
                    if file.suffix.lower() == ".lua":
                        text = file.read_text(encoding="utf-8-sig")
                        if SECRET.search(text) or NETWORK.search(text):
                            raise SystemExit(f"Review script for credentials before bundling: {file.name}")
                    name = hashlib.sha256(original.encode()).hexdigest()[:12] + "-" + file.name
                    target = ROOT / "assets" / name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(file, target)
                    info["included"] = True
                    assets.append({"original": original, "file": f"assets/{name}"})
    write_json({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "assets": assets,
        "external_dependencies": dependencies,
        "redacted_settings": removed,
        "excluded": [
            "Browser cache, cookies, login sessions, and browser profiles",
            "Stream keys, account tokens, account details, and WebSocket passwords",
            "Network URLs and custom browser docks (may contain credentials)",
            "Logs, crashes, updater caches, and service compatibility caches",
            "Plugin binaries, VST binaries, and recording/media videos",
        ],
    }, ROOT / "manifest.json")
    validate()
    print(f"Snapshot created: {len(list(SNAPSHOT.rglob('*')))} configuration entries.")


def validate():
    count = 0
    for file in SNAPSHOT.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix == ".ini":
            data = read_ini(file)
            for section in data.sections():
                for key, value in data[section].items():
                    if sensitive(key) and value:
                        raise SystemExit(f"Sensitive setting remains: {file.name}/{section}/{key}")
                    if NETWORK.search(value):
                        raise SystemExit(f"Network URL remains: {file.name}/{section}/{key}")
        else:
            data = json.loads(file.read_text(encoding="utf-8"))
            residual = []
            clean(data, residual, file.name)
            if residual:
                raise SystemExit(f"Sensitive settings remain in {file.name}: {residual}")
        count += 1
    if not count:
        raise SystemExit("Snapshot contains no configuration files.")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for asset in manifest["assets"]:
        if not (ROOT / asset["file"]).is_file():
            raise SystemExit(f"Missing bundled asset: {asset['file']}")
    print(f"Validated {count} configuration files; no populated credential fields or network URLs.")


def replace_paths(value, replacements):
    if isinstance(value, dict):
        return {key: replace_paths(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_paths(item, replacements) for item in value]
    return replacements.get(value, value) if isinstance(value, str) else value


def restore(target, dry_run):
    validate()
    if os.name == "nt" and not dry_run:
        processes = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"], text=True
        )
        if re.search(r'"obs(?:32|64)?\.exe"', processes, re.I):
            raise SystemExit("Close OBS before restoring settings.")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    asset_target = target / "portable-assets"
    replacements = {
        asset["original"]: str(asset_target / Path(asset["file"]).name)
        for asset in manifest["assets"]
    }
    files = sorted(file for file in SNAPSHOT.rglob("*") if file.is_file())
    if dry_run:
        print(f"Would restore {len(files)} settings files and {len(replacements)} assets to {target}")
        return
    backup = target.parent / (
        target.name + "-before-restore-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    )
    for source in files:
        destination = target / source.relative_to(SNAPSHOT)
        if destination.exists():
            previous = backup / source.relative_to(SNAPSHOT)
            previous.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, previous)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == ".ini":
            shutil.copy2(source, destination)
        else:
            data = json.loads(source.read_text(encoding="utf-8"))
            write_json(replace_paths(data, replacements), destination)
    for asset in manifest["assets"]:
        asset_target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / asset["file"], asset_target / Path(asset["file"]).name)
    print(f"Restored settings to {target}. Previous overwritten files, if any: {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "validate", "restore"])
    parser.add_argument("--target", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    default = Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "obs-studio"
    if args.action == "snapshot":
        snapshot(args.target or default)
    elif args.action == "validate":
        validate()
    else:
        restore(args.target or default, args.dry_run)


if __name__ == "__main__":
    main()
