/* Character restrictions from the pinned NetHack 5.0.0 src/role.c allow masks.
 * NetHack-derived restriction data retains NGPL; original JavaScript is MIT.
 * License boundary recorded by NetHack Atlas, 2026-10-06. See LICENSES.md.
 */
(function (root) {
  "use strict";
  // NetHack 5.0.0 src/role.c allow masks; update with the pinned engine version.
  const roles = {
    Archeologist: {
      genders: ["male", "female"],
      races: ["human", "dwarf", "gnome"],
      alignments: ["lawful", "neutral"],
    },
    Barbarian: {
      genders: ["male", "female"],
      races: ["human", "orc"],
      alignments: ["neutral", "chaotic"],
    },
    Caveman: {
      genders: ["male", "female"],
      races: ["human", "dwarf", "gnome"],
      alignments: ["lawful", "neutral"],
    },
    Healer: {
      genders: ["male", "female"],
      races: ["human", "gnome"],
      alignments: ["neutral"],
    },
    Knight: {
      genders: ["male", "female"],
      races: ["human"],
      alignments: ["lawful"],
    },
    Monk: {
      genders: ["male", "female"],
      races: ["human"],
      alignments: ["lawful", "neutral", "chaotic"],
    },
    Priest: {
      genders: ["male", "female"],
      races: ["human", "elf"],
      alignments: ["lawful", "neutral", "chaotic"],
    },
    Rogue: {
      genders: ["male", "female"],
      races: ["human", "orc"],
      alignments: ["chaotic"],
    },
    Ranger: {
      genders: ["male", "female"],
      races: ["human", "elf", "gnome", "orc"],
      alignments: ["neutral", "chaotic"],
    },
    Samurai: {
      genders: ["male", "female"],
      races: ["human"],
      alignments: ["lawful"],
    },
    Tourist: {
      genders: ["male", "female"],
      races: ["human"],
      alignments: ["neutral"],
    },
    Valkyrie: {
      genders: ["female"],
      races: ["human", "dwarf"],
      alignments: ["lawful", "neutral"],
    },
    Wizard: {
      genders: ["male", "female"],
      races: ["human", "elf", "gnome", "orc"],
      alignments: ["neutral", "chaotic"],
    },
  };
  const raceAlignments = {
    human: ["lawful", "neutral", "chaotic"],
    elf: ["chaotic"],
    dwarf: ["lawful"],
    gnome: ["neutral"],
    orc: ["chaotic"],
  };

  const races = Object.fromEntries(
    Object.entries(raceAlignments).map(([name, alignments]) => [
      name,
      { genders: ["male", "female"], alignments },
    ])
  );
  function choices(selection) {
    const role = roles[selection.role];
    const race = races[selection.race];
    return {
      races: role ? role.races : Object.keys(races),
      genders: ["male", "female"].filter(
        (value) =>
          (!role || role.genders.includes(value)) &&
          (!race || race.genders.includes(value))
      ),
      alignments: ["lawful", "neutral", "chaotic"].filter(
        (value) =>
          (!role || role.alignments.includes(value)) &&
          (!race || race.alignments.includes(value))
      ),
    };
  }
  function resolve(selection) {
    const result = { ...selection };
    const allowedRaces = choices({ role: result.role }).races;
    if (allowedRaces.length === 1) result.race = allowedRaces[0];
    else if (!allowedRaces.includes(result.race) && result.race !== "random")
      result.race = "random";
    const allowed = choices(result);
    for (const [field, options] of [
      ["gender", allowed.genders],
      ["alignment", allowed.alignments],
    ]) {
      if (options.length === 1) result[field] = options[0];
      else if (!options.includes(result[field]) && result[field] !== "random")
        result[field] = "";
    }
    return result;
  }
  function valid(selection) {
    if (selection.role !== "random" && !roles[selection.role]) return false;
    const allowed = choices(selection);
    return [
      ["race", allowed.races],
      ["gender", allowed.genders],
      ["alignment", allowed.alignments],
    ].every(
      ([field, options]) =>
        options.length > 0 &&
        (selection[field] === "random" || options.includes(selection[field]))
    );
  }
  const api = { roles, races, choices, resolve, valid };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.AtlasCharacter = Object.freeze(api);
})(typeof globalThis !== "undefined" ? globalThis : this);
