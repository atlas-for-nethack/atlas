// The Electron host for Windows and Linux. It does the jobs of native/App.swift: it
// starts the engine, relays the bridge and saves on quit. NetHack owns the game.
import { app, BrowserWindow, ipcMain, Menu, net, protocol, session, shell } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

type Body = Record<string, unknown>;

const env = process.env;
const windows = process.platform === "win32";
const selfTest = process.argv.includes("--self-test");
// ponytail: development checkout layout; packaging (Phase 3) moves resources.
const root = path.resolve(__dirname, "..", "..");
const runtime = path.join(root, "engine", "runtime");
const dataDir = env.ATLAS_DATA_DIR
  ? path.resolve(env.ATLAS_DATA_DIR)
  : path.join(app.getPath("appData"), "NetHack Atlas", "5.0");
// An isolated data folder also gets its own browser profile and instance lock.
if (env.ATLAS_DATA_DIR) app.setPath("userData", dataDir + "-electron");
const MODES = ["standard", "beginner", "explore", "pauper"];
const SAVE_SUFFIX = ".NetHack-saved-game";
const OPTIONS_FILE = "atlas.nethackrc";
const PAGE = "atlas://app/web/index.html";
const CSP =
  "default-src 'self'; img-src 'self' data: blob:; object-src 'none'; " +
  "base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
const SNAPSHOTS: Record<string, string> = {
  "room-shape": "room-shape.png", "oracle-minor-prompt": "oracle-minor.png",
  "oracle-major-prompt": "oracle-major.png", "oracle-reading": "oracle-reading.png",
  "court-beneath": "court-beneath.png", "yn-default-focus": "yn-default.png",
  "direction-bar": "direction.png", "actions-filter": "actions.png",
  "explore-creation": "explore-creation.png", "explore-help": "explore-help.png",
  "pauper-creation": "pauper-creation.png", "pauper-help": "pauper-help.png",
  "nudist-creation": "nudist-creation.png", "starting-conditions": "starting-conditions.png",
  "context-underfoot": "context.png", "read-selection": "read.png",
  "beginner-creation": "beginner-creation.png", "beginner-help": "beginner-help.png",
  "beginner-chest-visible": "beginner-chest.png",
  "prompt-scroll": "prompt-scroll.png", "prompt-potion": "prompt-potion.png",
  "prompt-book": "prompt-book.png", "pet-target-keyboard": "pet-target.png",
  "pet-name-prompt": "pet-name.png",
  "lantern-fixture": "lantern-fixture.png", "lantern-move": "lantern-move.png",
  "lantern-bars-fixture": "lantern-bars-fixture.png",
  "lantern-bars-blocked": "lantern-bars-blocked.png",
};

let win: BrowserWindow | null = null;
let engine: ChildProcess | null = null;
let pending = Buffer.alloc(0);
let events: Body[] = [];
let flushScheduled = false;
let ready = false;
let closing = false;
let stderrTail = "";
let playMode = "standard";
let currentInput = "";
const preferencesFile = path.join(app.getPath("userData"), "preferences.json");
let lastCharacterName = "Adventurer";

const modeDir = (mode: string) =>
  mode === "standard" ? dataDir : path.join(dataDir, mode[0].toUpperCase() + mode.slice(1));
const isInt = (value: unknown): value is number => Number.isSafeInteger(value);
const letters = (value: unknown) =>
  typeof value === "string" && /^[A-Za-z]{1,30}$/.test(value) && value.toLowerCase() !== "random"
    ? value : null;

function sameFile(a: string, b: string) {
  try {
    return fs.statSync(a).size === fs.statSync(b).size && fs.readFileSync(a).equals(fs.readFileSync(b));
  } catch {
    return false;
  }
}

// Windows reads its paths only from a portable sysconf beside the executable,
// so each mode folder holds an engine copy, refreshed when it differs (ADR 0002).
// Linux follows the Mac: the engine runs from the runtime and the mode folder
// gets only its data, a save folder and empty score files. As on Windows, game
// data is refreshed when it differs; sysconf and symbols are copied once.
function prepareModeFolder(mode: string) {
  const directory = modeDir(mode);
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  if (windows) {
    for (const name of fs.readdirSync(runtime)) {
      const from = path.join(runtime, name), to = path.join(directory, name);
      if (name.startsWith(".") || name.endsWith(".nethackrc") || !fs.statSync(from).isFile()) continue;
      const playerOwned = ["sysconf", "symbols", "record", "logfile", "xlogfile", "perm"].includes(name);
      if (playerOwned ? !fs.existsSync(to) : !sameFile(from, to)) fs.copyFileSync(from, to);
    }
  } else {
    for (const name of ["nhdat", "license", "symbols", "sysconf"]) {
      const from = path.join(runtime, name), to = path.join(directory, name);
      const playerOwned = name === "symbols" || name === "sysconf";
      if (playerOwned ? !fs.existsSync(to) : !sameFile(from, to)) fs.copyFileSync(from, to);
    }
    fs.mkdirSync(path.join(directory, "save"), { recursive: true });
    for (const name of ["record", "logfile", "xlogfile", "perm"]) {
      const to = path.join(directory, name);
      if (!fs.existsSync(to)) fs.writeFileSync(to, "", { mode: 0o600 });
    }
  }
  if (mode === "explore") {
    // Authorize upstream discovery mode only in its own mode folder (ADR 0001).
    const config = path.join(directory, "sysconf");
    const original = fs.readFileSync(config, "utf8");
    const kept = original.split(/\r?\n/).filter((line) => !/^\s*EXPLORERS\s*=/.test(line));
    const updated = kept.join("\n").replace(/^\n+|\n+$/g, "") + "\nEXPLORERS=*\n";
    if (updated !== original) fs.writeFileSync(config, updated);
  }
}

// Windows saves are NAME.NetHack-saved-game in the mode folder. Linux saves are
// save/<uid>NAME with an optional suffix, as on the Mac.
function savedPlayers(mode: string): string[] {
  const directory = windows ? modeDir(mode) : path.join(modeDir(mode), "save");
  const prefix = windows ? "" : String(process.getuid!());
  let names: string[];
  try {
    names = fs.readdirSync(directory).filter((name) =>
      windows ? name.endsWith(SAVE_SUFFIX) : name.startsWith(prefix));
  } catch {
    return [];
  }
  return names
    .flatMap((name) => {
      try {
        const stat = fs.statSync(path.join(directory, name));
        return stat.isFile() ? [{ name, time: stat.mtimeMs }] : [];
      } catch {
        return [];
      }
    })
    .sort((a, b) => b.time - a.time)
    .map(({ name }) => {
      let player = name.slice(prefix.length);
      for (const suffix of [".gz", ".Z", SAVE_SUFFIX, ".svh"])
        if (player.endsWith(suffix)) player = player.slice(0, -suffix.length);
      return player;
    })
    .filter(Boolean);
}
const savedGames = () => MODES.flatMap((mode) => savedPlayers(mode).map((name) => ({ name, mode })));

function tileManifest(): unknown[] {
  try {
    const object = JSON.parse(fs.readFileSync(path.join(root, "assets/tiles/manifest.json"), "utf8"));
    const list: Body[] = Array.isArray(object) ? object : object.tilesets ?? [];
    // Exercise a requested atlas in the isolated self-test.
    const index = list.findIndex((tileset) => tileset.id === env.ATLAS_TEST_TILESET);
    if (selfTest && index > 0) list.unshift(...list.splice(index, 1));
    return list;
  } catch {
    return [];
  }
}

function boot() {
  const games = savedGames();
  send({
    type: "boot", version: "5.0.0", tilesets: tileManifest(), hasSave: games.length > 0,
    selfTest, savedGames: games, playtest: null,
    testGender: selfTest ? env.ATLAS_TEST_GENDER ?? "female" : "",
    testMode: selfTest ? env.ATLAS_TEST_MODE ?? "standard" : "",
    testNudist: selfTest && env.ATLAS_TEST_NUDIST === "1",
    testBlind: selfTest && env.ATLAS_TEST_BLIND === "1",
    testDeaf: selfTest && env.ATLAS_TEST_DEAF === "1",
    testNoStartingPet: selfTest && env.ATLAS_TEST_NO_STARTING_PET === "1",
    testScenario: selfTest ? env.ATLAS_TEST_SCENARIO ?? "" : "",
    testRoomBounds: selfTest ? env.ATLAS_TEST_ROOM_BOUNDS ?? "" : "",
    testTerrainTiles: selfTest ? env.ATLAS_TEST_TERRAIN_TILES ?? "[]" : "[]",
    name: lastCharacterName,
  });
}

// The same 13 actions and limits as the Mac host. Anything else is dropped.
function receive(body: Body) {
  switch (body.action) {
    case "ready":
      ready = true;
      boot();
      flush();
      if (selfTest) {
        setTimeout(() => {
          if (!engine) return;
          snapshot(env.ATLAS_SNAPSHOT);
          console.log(`Atlas smoke-test watchdog: current input ${currentInput}`);
          write("save");
        }, 35000);
      }
      break;
    case "diagnostic": {
      if (!selfTest) return;
      if (env.ATLAS_DIAGNOSTICS) fs.appendFileSync(env.ATLAS_DIAGNOSTICS, JSON.stringify(body) + "\n");
      const name = typeof body.phase === "string" ? SNAPSHOTS[body.phase] : undefined;
      if (name && env.ATLAS_SNAPSHOT) snapshot(path.join(path.dirname(env.ATLAS_SNAPSHOT), name));
      if (body.phase === "complete") {
        setTimeout(() => snapshot(env.ATLAS_SNAPSHOT).finally(() => app.quit()), 300);
      }
      break;
    }
    case "start":
    case "load":
      launch(body, body.action === "load");
      break;
    case "key":
      if (isInt(body.key)) write(`key ${body.key}`);
      else if (typeof body.key === "string") sendKey(body.key);
      break;
    case "command": {
      const name = body.name;
      if (typeof name === "string" && name && Buffer.byteLength(name) < 80 && !/[\n\r\0]/.test(name))
        write(`command ${name}`);
      break;
    }
    case "input": {
      const text = typeof body.text === "string" ? body.text : "";
      write(`line ${Array.from(text).slice(0, 240).join("").replace(/[\n\r]/g, " ")}`);
      break;
    }
    case "position":
      if (isInt(body.x) && isInt(body.y) && body.x >= 1 && body.x < 80 && body.y >= 0 && body.y < 21)
        write(`position ${body.x} ${body.y}`);
      break;
    case "menu":
      if (body.cancel === true) write("menu cancel");
      else if (Array.isArray(body.selections)) {
        const ids = body.selections.flatMap((entry: Body) =>
          entry && isInt(entry.id) ? [`${entry.id}:${isInt(entry.count) ? entry.count : -1}`] : []);
        write("menu " + ids.join(","));
      }
      break;
    case "inspect":
      if (isInt(body.x) && isInt(body.y) && body.x >= 0 && body.x < 80 && body.y >= 0 && body.y < 21)
        write(`inspect ${body.x} ${body.y}`);
      break;
    case "save":
      if (engine) write("save");
      break;
    case "importTileset":
      // ponytail: the file dialog and import arrive with the window menu (#7).
      send({ type: "error", text: "Tileset import is not available in this version yet." });
      break;
    case "showSaveFolder":
      shell.openPath(engine ? modeDir(playMode) : dataDir);
      break;
  }
}

function launch(options: Body, restoring: boolean) {
  if (engine) return send({ type: "error", text: "Save the current expedition before starting another." });
  const mode = typeof options.mode === "string" ? options.mode : "standard";
  if (!MODES.includes(mode))
    return send({ type: "error", text: "Choose Standard, Beginner, Explore or Pauper for this adventure." });
  if (!windows && process.platform !== "linux")
    return send({ type: "error", text: "This version of Atlas starts the game on Windows and Linux only." });
  const available = savedPlayers(mode);
  if (restoring && available.length === 0)
    return send({ type: "error", text: "There is no saved adventure to continue." });
  const requested = typeof options.name === "string" ? options.name : undefined;
  if (restoring && requested !== undefined && !available.includes(requested))
    return send({ type: "error", text: "That saved adventure is no longer available." });
  const rawName = restoring ? requested ?? available[0] : requested ?? "Adventurer";
  const sanitized = rawName.replace(/[^A-Za-z0-9_]/g, "").slice(0, 24);
  const playerName = restoring ? rawName : sanitized || "Adventurer";
  if (!restoring && available.some((name) => name.toLowerCase() === playerName.toLowerCase()))
    return send({
      type: "error",
      text: `An adventure named ${playerName} is already saved. Continue that adventure or use a different name.`,
    });
  rememberName(playerName);
  playMode = mode;
  const directory = modeDir(mode);
  const gameOptions = ["color", "hilite_pet", "!autopickup", "time", "!news", "force_invmenu", "menustyle:full"];
  if (selfTest && ["0", "1", "3"].includes(env.ATLAS_TEST_NUMBER_PAD ?? ""))
    gameOptions.push(`number_pad:${env.ATLAS_TEST_NUMBER_PAD}`);
  const args = ["-u", playerName];
  if (!windows) args.push("-@");
  if (mode === "explore") args.push("-X");
  if (!restoring) {
    // Windows reads neither -p, -r nor -@, so every facet is an option there.
    if (windows)
      gameOptions.push(`role:${letters(options.role) ?? "random"}`, `race:${letters(options.race) ?? "random"}`);
    else
      for (const [field, flag] of [["role", "-p"], ["race", "-r"]]) {
        const value = letters(options[field]);
        if (value) args.push(flag, value);
      }
    if (mode === "pauper") gameOptions.push("pauper");
    if (mode !== "pauper" && options.nudist === true) gameOptions.push("nudist");
    if (options.blind === true) gameOptions.push("blind");
    if (options.deaf === true) gameOptions.push("deaf");
    if (options.noStartingPet === true) gameOptions.push("pettype:none");
    // Linux omits an unchosen facet, as on the Mac; -@ picks it at random.
    for (const [field, option] of [["gender", "gender"], ["alignment", "align"]]) {
      const value = letters(options[field]) ?? (windows ? "random" : null);
      if (value) gameOptions.push(`${option}:${value}`);
    }
  }
  try {
    prepareModeFolder(mode);
    if (windows) fs.writeFileSync(path.join(directory, OPTIONS_FILE), `OPTIONS=${gameOptions.join(",")}\n`);
  } catch (error) {
    return send({ type: "error", text: `Could not prepare the game: ${(error as Error).message}` });
  }
  pending = Buffer.alloc(0);
  stderrTail = "";
  closing = false;
  const child = spawn(windows ? path.join(directory, "nethack.exe") : path.join(runtime, "nethack"), args, {
    cwd: directory,
    env: windows
      // A relative name: Windows keeps option file names under 128 characters.
      ? { ...env, NETHACKOPTIONS: "@" + OPTIONS_FILE, ATLAS_PLAY_MODE: mode, TERM: "dumb" }
      : { ...env, NETHACKDIR: directory, HACKDIR: directory, HOME: directory,
          NETHACKOPTIONS: gameOptions.join(","), ATLAS_PLAY_MODE: mode, TERM: "dumb" },
    windowsHide: true,
  });
  engine = child;
  child.stdout!.on("data", consume);
  child.stderr!.on("data", (data: Buffer) => { stderrTail = (stderrTail + data.toString()).slice(-8000); });
  child.stdin!.on("error", (error) =>
    send({ type: "error", text: `The game connection closed: ${error.message}` }));
  child.on("error", (error) => {
    if (engine === child) engine = null;
    send({ type: "error", text: error.message });
  });
  child.on("close", (code) => {
    if (engine !== child) return;
    engine = null;
    const games = savedGames();
    send({ type: "exit", code: code ?? -1, hasSave: games.length > 0, detail: stderrTail, savedGames: games });
    boot();
    if (closing) win?.close();
  });
  if (selfTest) console.log(`Atlas engine pid ${child.pid}`);
  send({ type: "started", name: playerName, mode });
}

function consume(data: Buffer) {
  pending = Buffer.concat([pending, data]);
  let end: number;
  while ((end = pending.indexOf(10)) >= 0) {
    const line = pending.subarray(0, end);
    pending = pending.subarray(end + 1);
    if (selfTest && env.ATLAS_DIAGNOSTICS)
      fs.appendFileSync(env.ATLAS_DIAGNOSTICS + ".engine.jsonl", Buffer.concat([line, Buffer.from("\n")]));
    let event: unknown;
    try {
      event = JSON.parse(line.toString("utf8"));
    } catch {
      event = null;
    }
    if (event && typeof event === "object" && !Array.isArray(event)) {
      const object = event as Body;
      if (object.type === "input") currentInput = typeof object.kind === "string" ? object.kind : "";
      send(object);
    } else if (line.toString().trim()) {
      stderrTail = (stderrTail + line.toString() + "\n").slice(-8000);
    }
  }
  if (pending.length > 8 * 1024 * 1024) {
    pending = Buffer.alloc(0);
    send({ type: "error", text: "The game returned an oversized message." });
  }
}

function send(event: Body) {
  if (selfTest && event.type === "error") console.log(`Atlas error: ${event.text}`);
  events.push(event);
  if (ready && !flushScheduled) {
    flushScheduled = true;
    setTimeout(flush, 16);
  }
}

function flush() {
  flushScheduled = false;
  if (!ready || events.length === 0 || !win) return;
  const batch = JSON.stringify(events);
  events = [];
  win.webContents.executeJavaScript(`window.receiveNative(${batch});`)
    .catch((error) => console.error(`Atlas UI: ${error}`));
}

function write(command: string) {
  if (engine?.stdin?.writable) engine.stdin.write(command + "\n");
}

function sendKey(key: string) {
  const keys: Record<string, number> = {
    ArrowUp: 107, ArrowDown: 106, ArrowLeft: 104, ArrowRight: 108, Enter: 10,
    Return: 10, Escape: 27, Backspace: 8, Tab: 9, Space: 32,
  };
  const bytes = Buffer.from(key);
  if (key in keys) write(`key ${keys[key]}`);
  else if (bytes.length === 1) write(`key ${bytes[0]}`);
}

function rememberName(name: string) {
  lastCharacterName = name;
  if (selfTest) return;
  try {
    fs.writeFileSync(preferencesFile, JSON.stringify({ lastCharacterName }));
  } catch {}
}

async function snapshot(file: string | undefined) {
  if (!file || !win) return;
  const image = await win.webContents.capturePage();
  fs.writeFileSync(file, image.toPNG());
}

function createWindow() {
  const browserSession = selfTest ? session.fromPartition("atlas-self-test") : session.defaultSession;
  browserSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  // Serve only the interface and its artwork, under a local-only policy.
  browserSession.protocol.handle("atlas", async (request) => {
    try {
      const { host, pathname } = new URL(request.url);
      const file = path.normalize(path.join(root, decodeURIComponent(pathname)));
      if (host !== "app" || !["web", "assets"].some((folder) => file.startsWith(path.join(root, folder) + path.sep)))
        return new Response(null, { status: 404 });
      const response = await net.fetch(pathToFileURL(file).toString());
      const headers = new Headers(response.headers);
      headers.set("Content-Security-Policy", CSP);
      return new Response(response.body, { status: response.status, headers });
    } catch {
      return new Response(null, { status: 404 });
    }
  });
  win = new BrowserWindow({
    width: 1440, height: 930, minWidth: 1000, minHeight: 700,
    title: "Atlas for NetHack", backgroundColor: "#090c11",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true, sandbox: true, nodeIntegration: false, session: browserSession,
    },
  });
  win.webContents.on("will-navigate", (event) => event.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  if (selfTest) win.webContents.on("console-message", (details) => console.log(`Atlas UI: ${details.message}`));
  // The close button and Alt+F4 save first; the engine's exit closes the window.
  win.on("close", (event) => {
    if (!engine) return;
    event.preventDefault();
    if (closing) return;
    closing = true;
    write("save");
    setTimeout(() => {
      if (!closing || !engine) return;
      closing = false;
      send({ type: "error", text: "Finish the current game prompt, then save and quit again. Your game is still running." });
    }, 8000);
  });
  // Late engine events can still be queued; flush and snapshot skip a closed window.
  win.on("closed", () => { win = null; });
  win.loadURL(PAGE);
}

// A self-test fails on any main-process exception instead of showing a dialog.
if (selfTest) {
  const fail = (error: unknown) => {
    console.error(`Atlas main-process failure: ${error instanceof Error ? error.stack : error}`);
    app.exit(1);
  };
  process.on("uncaughtException", fail);
  process.on("unhandledRejection", fail);
}
protocol.registerSchemesAsPrivileged([
  { scheme: "atlas", privileges: { standard: true, secure: true, supportFetchAPI: true } },
]);
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.focus();
  });
  if (!selfTest) {
    try {
      lastCharacterName = JSON.parse(fs.readFileSync(preferencesFile, "utf8")).lastCharacterName ?? lastCharacterName;
    } catch {}
  }
  ipcMain.on("atlas", (event, body) => {
    if (event.sender !== win?.webContents || event.senderFrame?.parent !== null ||
        !event.senderFrame.url.startsWith("atlas://app/")) return;
    if (body && typeof body === "object" && typeof body.action === "string") receive(body);
  });
  app.on("window-all-closed", () => app.quit());
  app.whenReady().then(() => {
    // No default menu: no reload, developer tools or Ctrl+letter accelerators.
    Menu.setApplicationMenu(null);
    fs.mkdirSync(dataDir, { recursive: true });
    createWindow();
  });
}
