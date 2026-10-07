/* Shared protocol rules. Also loaded directly by the focused Node tests. */
(function (root) {
  "use strict";
  const rules = {
    answerForKey(prompt, key) {
      if (typeof key === "number") key = String.fromCharCode(key);
      if (key === "Escape" || key === "\x1b") return "\x1b";
      if (key === "Enter" || key === "\n" || key === "\r" || key === " ") {
        key = prompt.default || "\n";
      }
      if (typeof key !== "string" || key.length !== 1) return null;
      if (prompt.choices?.includes("#") && /^[0-9]$/.test(key)) return key;
      // Hidden choices after ESC are valid keyboard answers, but not buttons.
      return !prompt.choices || prompt.choices.includes(key) ? key : null;
    },
    directionKey(prompt, key) {
      if (key === ".") return prompt.selfKey || ".";
      const index = "hykulnjb><".indexOf(key);
      return index >= 0 ? (prompt.directionKeys || "hykulnjb><")[index] : key;
    },
    movementKey(prompt, direction, run = false) {
      const key = this.directionKey(prompt, direction);
      // Upstream binds running to uppercase letters or Meta keypad digits.
      return !run ? key : /^[0-9]$/.test(key)
        ? key.charCodeAt(0) | 128 : key.toUpperCase();
    },
    adjacentDirection(player, target) {
      const dx = target.x - player.x,
        dy = target.y - player.y;
      if (
        !Number.isInteger(dx) ||
        !Number.isInteger(dy) ||
        Math.abs(dx) > 1 ||
        Math.abs(dy) > 1 ||
        (!dx && !dy)
      )
        return null;
      return [
        ["y", "k", "u"],
        ["h", null, "l"],
        ["b", "j", "n"],
      ][dy + 1][dx + 1];
    },
    filterCommands(commands, query) {
      const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
      const text = (command) =>
        [command.name, command.description, ...(command.keys || [])]
          .join(" ")
          .toLowerCase();
      const rank = (command) =>
        !words.length || command.name.toLowerCase().startsWith(words[0])
          ? 0
          : 1;
      return commands
        .filter((command) =>
          words.every((word) => text(command).includes(word))
        )
        .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
    },
    menuCount(prefix) {
      const value = Number(prefix);
      return Number.isSafeInteger(value) && value > 0 ? value : -1;
    },
  };
  if (typeof module === "object" && module.exports) module.exports = rules;
  else root.AtlasInput = Object.freeze(rules);
})(typeof globalThis !== "undefined" ? globalThis : this);
