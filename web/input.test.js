"use strict";
const assert = require("node:assert/strict");
const rules = require("./input.js");
const yn = { choices: "yn", default: "n" };
assert.equal(
  rules.answerForKey(yn, "x"),
  null,
  "invalid choice must not close an engine prompt"
);
assert.equal(rules.answerForKey(yn, "y"), "y");
assert.equal(rules.answerForKey(yn, "Enter"), "n");
assert.equal(rules.answerForKey(yn, " "), "n");
assert.equal(rules.answerForKey(yn, "Escape"), "\x1b");
assert.equal(
  rules.answerForKey({ choices: "yn\x1bq", default: "n" }, "q"),
  "q",
  "hidden choices remain valid"
);
assert.equal(
  rules.answerForKey({ choices: "", default: "" }, "Enter"),
  "\n",
  "unrestricted prompts accept Return"
);
assert.equal(rules.answerForKey({ choices: "", default: "" }, "x"), "x");
assert.equal(
  rules.answerForKey({ choices: "yn", default: "" }, "Enter"),
  null,
  "no default means Return cannot unblock this prompt"
);
assert.equal(rules.menuCount("12"), 12);
assert.equal(rules.menuCount(""), -1);
assert.equal(rules.menuCount("0"), -1);
assert.equal(rules.menuCount("99999999999999999999"), -1);

assert.equal(
  rules.answerForKey({ choices: "yn#", default: "n" }, "2"),
  "2",
  "quantity prompt accepts numeric prefixes"
);
assert.equal(
  rules.answerForKey({ choices: "yn", default: "n" }, "2"),
  null,
  "ordinary yes/no cannot accept quantity prefixes"
);
console.log(
  "Input protocol tests passed: valid/invalid answers, defaults, hidden choices, unrestricted input, quantities."
);

// Compass and arrow controls must follow the engine's active keypad mode.
assert.equal(rules.directionKey({ directionKeys: "47896321><" }, "k"), "8");
assert.equal(rules.directionKey({ directionKeys: "41236987><" }, "k"), "2");
assert.equal(rules.directionKey({ directionKeys: "47896321><" }, "y"), "7");
assert.equal(rules.directionKey({ directionKeys: "47896321><" }, ">"), ">");
assert.equal(rules.directionKey({ selfKey: "5" }, "."), "5");
assert.equal(rules.directionKey({}, "k"), "k");
for (const bindings of ["hykulnjb><", "47896321><", "41236987><", "hzkulnjb><"]) {
  for (const [index, direction] of [..."hykulnjb"].entries()) {
    const prompt = { directionKeys: bindings };
    assert.equal(rules.movementKey(prompt, direction), bindings[index]);
    assert.equal(rules.movementKey(prompt, direction, true),
      /^[0-9]$/.test(bindings[index]) ? bindings.charCodeAt(index) | 128 : bindings[index].toUpperCase(),
      "running follows the advertised engine letter/keypad binding");
  }
}
assert.equal(rules.movementKey({}, "k", true), "K");

assert.equal(rules.adjacentDirection({ x: 10, y: 10 }, { x: 9, y: 9 }), "y");
assert.equal(rules.adjacentDirection({ x: 10, y: 10 }, { x: 11, y: 11 }), "n");
assert.equal(rules.adjacentDirection({ x: 10, y: 10 }, { x: 11, y: 10 }), "l");
assert.equal(rules.adjacentDirection({ x: 10, y: 10 }, { x: 10, y: 10 }), null);
assert.equal(rules.adjacentDirection({ x: 10, y: 10 }, { x: 12, y: 10 }), null);
const commands = [
  { name: "kick", description: "kick something", keys: ["Ctrl+D"] },
  { name: "sit", description: "sit down", keys: [] },
  { name: "search", description: "search nearby", keys: ["s"] },
  { name: "cast", description: "cast a spell", keys: ["Z"] },
];
assert.deepEqual(
  rules.filterCommands(commands, "s").map((c) => c.name),
  ["search", "sit", "cast", "kick"]
);
assert.deepEqual(
  rules.filterCommands(commands, " CTRL+d ").map((c) => c.name),
  ["kick"]
);
assert.deepEqual(
  rules.filterCommands(commands, "cast spell").map((c) => c.name),
  ["cast"]
);
assert.equal(rules.filterCommands(commands, "nonexistent").length, 0);
console.log("Mouse adjacency and action filtering tests passed.");
