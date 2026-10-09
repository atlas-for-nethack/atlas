"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// Execute the complete production app and its registered handlers. Images and
// animation frames are delivered explicitly so callback order is deterministic.
// The injected accessor only exposes closure state in this in-memory test copy.
function app({ host = false, platform = "MacIntel" } = {}) {
  const elements = new Map(), images = [], frames = [], sent = [], storage = new Map();
  let document;
  class Element {
    constructor(id = "", tagName = "DIV") {
      this.id = id; this.tagName = tagName; this.style = {}; this.dataset = {};
      this.children = []; this.listeners = {}; this.value = ""; this.textContent = "";
      this.open = false; this.clientWidth = 800; this.clientHeight = 600;
      this.offsetLeft = this.offsetTop = 0;
      const classes = new Set();
      this.classList = { add: (s) => classes.add(s), remove: (s) => classes.delete(s),
        toggle: (s, on) => on ? classes.add(s) : classes.delete(s), contains: (s) => classes.has(s) };
    }
    get options() { return this.children; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
    dispatchEvent(event) { for (const callback of this.listeners[event.type] || []) callback(event); }
    querySelectorAll() { return []; }
    querySelector() { return null; }
    setAttribute() {}
    contains(other) { return this.children.includes(other); }
    focus() { document.activeElement = this; }
    close() { this.open = false; }
    showModal() { this.open = true; }
    getBoundingClientRect() { return { left: 0, top: 0, right: 800, bottom: 600 }; }
    getContext() { return new Proxy({}, { get: (o, k) => o[k] || (() => {}), set: (o, k, v) => (o[k] = v, true) }); }
  }
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, new Element(id, id === "dungeon" ? "CANVAS" : "DIV"));
    return elements.get(id);
  };
  document = new Element();
  document.getElementById = get;
  document.body = new Element();
  document.createElement = (tag) => new Element("", tag.toUpperCase());
  document.querySelector = (query) => query === "dialog[open]"
    ? [...elements.values()].find((e) => e.id.endsWith("-dialog") && e.open) || null : null;
  document.activeElement = get("dungeon");
  get("player-role").value = "Wizard";
  for (const field of ["race", "gender", "alignment"]) get("player-" + field).value = "random";
  const bridge = { postMessage: (message) => sent.push(message) };
  const hosts = { true: { atlasHost: bridge }, false: { webkit: { messageHandlers: { nethack: bridge } } }, none: {} };
  const window = { ...hosts[host], navigator: { platform }, addEventListener() {}, devicePixelRatio: 1 };
  const context = vm.createContext({ window, document, location: { search: "" }, URLSearchParams,
    AtlasInput: require("./input.js"), AtlasCharacter: require("./character.js"),
    AtlasTiles: { paintMap: () => false, paint: () => false },
    localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    requestAnimationFrame: (callback) => frames.push(callback), setTimeout: () => 1, clearTimeout() {},
    Image: class { constructor() { images.push(this); } }, console });
  const source = fs.readFileSync(process.env.ATLAS_APP_SOURCE || __dirname + "/app.js", "utf8")
    .replace(/\r\n/g, "\n"); // Windows checkouts
  assert(source.endsWith("})();\n"), "test accessor insertion follows the production closure");
  vm.runInContext(source.slice(0, -6) + "globalThis.appState = state;\n})();\n", context);
  const receive = (event) => window.receiveNative(event);
  const select = (id) => { get("tileset-select").value = id; get("tileset-select").onchange({ target: get("tileset-select") }); };
  const press = (key, modifiers = {}) => {
    const before = sent.length;
    document.dispatchEvent({ type: "keydown", key, shiftKey: false, ctrlKey: false,
      metaKey: false, altKey: false, preventDefault() {}, ...modifiers });
    return sent.slice(before).map((m) => ({ ...m }));
  };
  return { get, images, sent, receive, select, press, state: context.appState,
    preference: () => JSON.parse(storage.get("atlasPreferences") || "{}"),
    render: () => { while (frames.length) frames.shift()(); } };
}

const choices = ["A", "B"].map((id) => ({ id, name: "Atlas " + id, path: id + ".png", tileWidth: 32, tileHeight: 32 }));
function atlasApp() { const a = app(); a.receive({ type: "boot", tilesets: choices }); return a; }
function finish(image) { image.complete = true; image.onload(); }
function assertChoice(a, id) {
  assert.equal(a.get("tileset-select").value, id);
  assert.equal(a.preference().tileset, id);
  assert.equal(a.state.ascii, id === "ascii");
  assert.equal(a.state.selectedAtlas?.id || null, id === "ascii" ? null : id);
  assert.equal(a.get("tileset-label").textContent, id === "ascii" ? "Typography / ASCII" : "Atlas " + id);
  if (id === "ascii") assert.equal(a.state.atlas, null);
}
{
  const a = atlasApp(); a.select("B"); finish(a.images[1]); finish(a.images[0]);
  assertChoice(a, "B"); assert.equal(a.state.atlas, a.images[1]);
}
{
  const a = atlasApp(); a.select("ascii"); finish(a.images[0]); a.images[0].onerror();
  assertChoice(a, "ascii"); assert.equal(a.get("toast").textContent, "");
}
{
  const a = atlasApp(); a.select("B"); finish(a.images[1]); a.images[0].onerror();
  assertChoice(a, "B"); assert.equal(a.get("toast").textContent, "");
}
{
  const a = atlasApp(); a.select("B"); a.select("A"); a.select("A");
  finish(a.images[3]); a.images[2].onerror(); finish(a.images[1]); finish(a.images[0]);
  assertChoice(a, "A"); assert.equal(a.state.atlas, a.images[3]);
}
{
  const a = atlasApp(); a.images[0].onerror(); assertChoice(a, "ascii");
  assert.match(a.get("toast").textContent, /could not be loaded/);
  finish(a.images[0]); assertChoice(a, "ascii");
  a.receive({ type: "tilesetImported", persistent: true, tileset: { ...choices[1], id: "custom", name: "Custom" } });
  finish(a.images.at(-1)); assert.equal(a.state.selectedAtlas.id, "custom");
  assert.equal(a.preference().tileset, "custom"); assert.equal(a.get("tileset-label").textContent, "Custom");
}
console.log("Actual app selection tests passed: out-of-order success/failure, ASCII, repeats, fallback and import.");

for (const directionKeys of ["hykulnjb><", "47896321><", "41236987><", "hzkulnjb><"]) {
  const a = app(); a.receive({ type: "started" });
  const keys = ["ArrowLeft", "Home", "ArrowUp", "PageUp", "ArrowRight", "PageDown", "ArrowDown", "End"];
  for (const [index, control] of keys.entries()) {
    for (const shiftKey of [false, true]) {
      a.receive({ type: "input", kind: "key", command: true, directionKeys });
      const expected = shiftKey ? /^[0-9]$/.test(directionKeys[index])
        ? directionKeys.charCodeAt(index) | 128 : directionKeys[index].toUpperCase() : directionKeys[index];
      assert.deepEqual(a.press(control, { shiftKey }), [{ action: "key", key: expected }]);
      assert.deepEqual(a.press(control), [], "cannot send another movement before an engine wait");
    }
    for (const kind of ["direction", "targeting"]) {
      a.receive({ type: "input", kind: kind === "direction" ? "yn" : "key", command: false,
        choices: "", [kind]: true, directionKeys });
      assert.deepEqual(a.press(control, { shiftKey: true }), [{ action: "key", key: directionKeys[index] }],
        "direction/targeting navigation retains its existing plain direction semantics");
    }
  }
  a.receive({ type: "input", kind: "key", command: false, targeting: true, directionKeys });
  assert.deepEqual(a.press("Enter"), [{ action: "position", x: 40, y: 10 }]);
  for (const kind of ["direction", "targeting"]) {
    a.receive({ type: "input", kind: kind === "direction" ? "yn" : "key", command: false, [kind]: true, directionKeys });
    assert.deepEqual(a.press("Escape"), [{ action: "key", key: "\x1b" }]);
  }
  a.receive({ type: "input", kind: "yn", choices: "yn", default: "n" });
  assert.deepEqual(a.press("ArrowUp"), [], "ordinary confirmation does not navigate");
  a.press("Escape");
  a.receive({ type: "input", kind: "key", command: true, directionKeys });
  assert.deepEqual(a.press("k"), [{ action: "key", key: "k" }], "original engine letter commands pass through unchanged");
  for (const [index, control] of keys.entries()) {
    const neighbors = [[-1, 0], [-1, -1], [0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1]];
    const [dx, dy] = neighbors[index];
    a.receive({ type: "input", kind: "key", command: true, directionKeys });
    const before = a.sent.length;
    a.get("dungeon").dispatchEvent({ type: "click", detail: 1,
      clientX: (40 + dx + 0.5) * 40, clientY: (10 + dy + 0.5) * 40 });
    assert.deepEqual(a.sent.slice(before).map((m) => ({ ...m })), [{ action: "key", key: directionKeys[index] }],
      "mouse movement and keyboard control " + control + " dispatch the same engine binding");
  }
}
console.log("Actual app keyboard/mouse tests passed: advertised default, keypad 1/3 and swapped letters, all eight directions, running and prompt/targeting guards.");

const a = app();
function location(value, materials = []) {
  a.receive({ type: "clear", window: "map" });
  for (const [x, material] of materials.entries()) a.receive({ type: "cell", x: x + 1, y: 0, tile: 1291, char: ".", material });
  a.receive({ type: "status", name: "dungeon-level", value }); a.receive({ type: "statusFlush" });
  return a.get("location-detail").textContent;
}
assert.match(location("Dlvl: 3", ["mines-built"]), /^The Gnomish Mines/);
assert.match(location("Dlvl: 30", ["vlad"]), /^Vlad’s Tower/);
assert.match(location("Dlvl: 30", ["valley"]), /^Gehennom/);
assert.match(location("Home 3", ["baalz"]), /^The Quest/, "Quest status overrides reused infernal materials");
assert.match(location("Fire", ["gehennom"]), /^The Plane of Fire/);
for (const plane of ["Earth", "Air", "Water"]) assert.match(location(plane), new RegExp("^The Plane of " + plane));
assert.match(location("Astral"), /^The Astral Plane/);
assert.match(location("Tutorial: 1"), /^Tutorial/);
assert.match(location("Fort Ludios"), /^Fort Ludios/);
assert.equal(location("Dlvl: 3", ["quest-earth", "medusa"]), "Explore. Observe. Survive.", "shared artwork does not disclose named special levels");
assert.equal(location("Dlvl: 3"), "Explore. Observe. Survive.", "unclassified branch must not assert Dungeons of Doom");
a.receive({ type: "boot", playtest: { label: "Selected fixture", mode: "inspection" } });
assert.equal(location("Home 3"), "Test start: Selected fixture · starting map revealed");
console.log("Actual app subtitle tests passed: disclosed broad context, reused materials, neutral fallback, branch changes and playtest labels.");

{
  // Each host shows its own shortcut modifier and keeps the other one free for the engine.
  for (const host of [false, true]) {
    const a = app({ host }), mod = host ? { ctrlKey: true } : { metaKey: true }, label = host ? "Ctrl+" : "⌘";
    a.receive({ type: "started" });
    for (const [id, letter] of [["actions-shortcut", "K"], ["save-shortcut", "S"],
      ["help-actions-shortcut", "K"], ["help-save-shortcut", "S"]])
      assert.equal(a.get(id).textContent, label + letter);
    assert.ok(a.get("actions-button").title.endsWith(`(${label}K)`));
    a.receive({ type: "input", kind: "key", command: true });
    assert.deepEqual(a.press("k"), [{ action: "key", key: "k" }], "the bridge carries engine keys");
    a.receive({ type: "input", kind: "key", command: true });
    assert.deepEqual(a.press("k", mod), [], "the action list shortcut sends nothing to the engine");
    assert.equal(a.get("actions-dialog").open, true);
    a.get("actions-dialog").close();
    const engineCtrl = host ? ["d"] : ["d", "k", "s"];
    for (const letter of engineCtrl) {
      a.receive({ type: "input", kind: "key", command: true });
      assert.deepEqual(a.press(letter, { ctrlKey: true }),
        [{ action: "key", key: String.fromCharCode(letter.charCodeAt(0) & 31) }], "Ctrl+" + letter + " reaches the engine");
    }
    a.receive({ type: "input", kind: "key", command: true });
    if (host) assert.ok(!a.press("s", { ctrlKey: true, altKey: true }).some((m) => m.action === "save"),
      "AltGr (Ctrl+Alt) never saves");
    assert.deepEqual(a.press("s", mod), [{ action: "save" }]);
  }
}
// A browser preview has no host, so its labels follow the browser's platform.
assert.equal(app({ host: "none", platform: "Win32" }).get("actions-shortcut").textContent, "Ctrl+K");
assert.equal(app({ host: "none", platform: "MacIntel" }).get("actions-shortcut").textContent, "⌘K");
console.log("Actual app bridge tests passed: host object or WebKit handler, shortcut labels, Ctrl shortcuts and engine Ctrl keys.");
