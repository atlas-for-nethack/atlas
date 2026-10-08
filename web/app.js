"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const canvas = $("dungeon"),
    ctx = canvas.getContext("2d", { alpha: false });
  const native = !!window.webkit?.messageHandlers?.nethack;
  const replay = !native && new URLSearchParams(location.search).has("replay");
  const preview =
    !native && (replay || new URLSearchParams(location.search).has("preview"));
  if (native) document.body.classList.add("native-app");
  const state = {
    width: 80,
    height: 21,
    cells: new Map(),
    player: { x: 40, y: 10 },
    cursor: { x: 40, y: 10 },
    tileSize: 40,
    active: false,
    waiting: false,
    command: false,
    commandInput: null,
    commands: [],
    contextActions: [],
    pendingAction: false,
    input: null,
    menuCount: "",
    stats: {},
    experience: null,
    messages: [],
    promptMessages: [],
    atlas: null,
    tilesets: [],
    selectedAtlas: null,
    atlasRequest: 0,
    ascii: false,
    follow: true,
    grid: true,
    hover: null,
    mapPointerInside: false,
    renderPending: false,
    startPending: false,
    mode: null,
  };
  let toastTimer, hoverTimer;
  let mapPointerPosition = null;
  let savedPreferences = {};
  try {
    savedPreferences = JSON.parse(
      localStorage.getItem("atlasPreferences") || "{}"
    );
  } catch {}
  if (native) delete savedPreferences.customAtlas;
  const smoke = { enabled: false, stage: "idle", cells: 0, inspected: false };
  function preference(key, value) {
    savedPreferences[key] = value;
    try {
      localStorage.setItem(
        "atlasPreferences",
        JSON.stringify(savedPreferences)
      );
      return true;
    } catch {
      return false;
    }
  }
  function diagnostic(phase, ok, detail) {
    send({ action: "diagnostic", phase, ok, detail });
  }
  // Report asynchronous renderer failures in isolated native tests instead of
  // leaving only a watchdog timeout and a blank screenshot.
  window.addEventListener("error", event => {
    if (smoke.enabled) diagnostic("javascript", false,
      `${event.message} at ${event.filename}:${event.lineno}:${event.colno}`);
  });
  // This opt-in path exercises the same controls as a player, against the real engine.
  function smokeSnapshot() {
    return {
      x: state.player.x,
      y: state.player.y,
      turn: Number(stat("time", "moves")),
    };
  }
  function smokeCheck(phase, ok, detail) {
    if (!ok) smoke.failed = true;
    diagnostic(phase, ok, detail);
  }
  function smokePress(key) {
    canvas.focus();
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true })
    );
  }
  function smokeClickTile(x, y) {
    const rect = canvas.getBoundingClientRect();
    const [left,top] = mapPadding();
    canvas.dispatchEvent(
      new MouseEvent("click", {
        bubbles: true,
        detail: 1,
        clientX: rect.left + left + (x + 0.5) * state.tileSize,
        clientY: rect.top + top + (y + 0.5) * tileHeight(),
      })
    );
  }
  function smokeMove(mode = "keyboard") {
    smoke.beforeMove = smokeSnapshot();
    const directions = [
      ["ArrowRight", 1, 0],
      ["ArrowLeft", -1, 0],
      ["ArrowDown", 0, 1],
      ["ArrowUp", 0, -1],
      ["PageDown", 1, 1],
      ["End", -1, 1],
      ["PageUp", 1, -1],
      ["Home", -1, -1],
    ];
    if (mode === "mouse") directions.unshift(...directions.splice(4));
    const target = directions
      .map(([key, dx, dy]) => ({
        key,
        x: state.player.x + dx,
        y: state.player.y + dy,
      }))
      .find((p) => {
        const cell = state.cells.get(`${p.x},${p.y}`);
        return (
          cell?.char === "." && !cell.pet && [1291, 1292].includes(cell.tile)
        );
      });
    if (!target) {
      smokeCheck(
        "arrow-movement",
        false,
        "No empty adjacent floor available for movement verification"
      );
      smoke.stage = "inspect";
      smoke.beforeInspect = smokeSnapshot();
      inspectCell(state.player.x, state.player.y);
      return;
    }
    smoke.target = target;
    smoke.stage = mode === "mouse" ? "mouseMoving" : "moving";
    setTimeout(
      () =>
        mode === "mouse"
          ? smokeClickTile(target.x, target.y)
          : smokePress(target.key),
      100
    );
  }
  function smokeContinueAfterChest() {
    if (smoke.mode === "pauper") {
      smokeMove();
      return;
    }
    smoke.beforeRead = smokeSnapshot();
    smoke.stage = "readSelection";
    setTimeout(() => key("r"), 100);
  }
  function smokeInspectNextChest() {
    const candidate = smoke.chestCandidates.shift();
    if (!candidate) {
      smokeCheck("beginner-chest-visible", false,
        "No visible named supply chest was found near the starting room");
      smokeContinueAfterChest();
      return;
    }
    smoke.chestCandidate = candidate;
    inspectCell(candidate.x, candidate.y);
  }
  function smokeFindChest() {
    const start = state.player;
    smoke.chestOrigin = { ...start };
    smoke.chestCandidates = [...state.cells.values()]
      .filter((cell) => cell.char === "(" && !cell.pet)
      .sort((a, b) =>
        Math.max(Math.abs(a.x - start.x), Math.abs(a.y - start.y)) -
        Math.max(Math.abs(b.x - start.x), Math.abs(b.y - start.y)));
    smoke.stage = "inspectChest";
    smokeInspectNextChest();
  }
  function smokePathToChest(target) {
    const start = smoke.chestOrigin;
    const queue = [{ x: start.x, y: start.y, path: [] }];
    const seen = new Set([`${start.x},${start.y}`]);
    const steps = [[1, 0], [-1, 0], [0, 1], [0, -1],
      [1, 1], [-1, 1], [1, -1], [-1, -1]];
    for (let i = 0; i < queue.length; i++) {
      const current = queue[i];
      for (const [dx, dy] of steps) {
        const x = current.x + dx, y = current.y + dy;
        const key = `${x},${y}`;
        if (seen.has(key)) continue;
        const cell = state.cells.get(key);
        if (!cell || cell.pet ||
          !(x === target.x && y === target.y) && cell.char !== ".") continue;
        const path = [...current.path, { x, y }];
        if (x === target.x && y === target.y) return path;
        seen.add(key);
        queue.push({ x, y, path });
      }
    }
    return null;
  }
  function smokeHoverFocus() {
    const map = $("map-container"), rect = canvas.getBoundingClientRect();
    const [left,top] = mapPadding();
    const painter = AtlasTiles.paintMap;
    let observed;
    AtlasTiles.paintMap = (...args) => { observed = args[6]; return painter(...args); };
    const point = (x,y) => {
      map.dispatchEvent(new MouseEvent("mousemove", {bubbles:true,
        clientX:rect.left+left+(x+.5)*state.tileSize,
        clientY:rect.top+top+(y+.5)*tileHeight()}));
      clearTimeout(hoverTimer);
      render();
      return observed;
    };
    try {
      const hero = point(state.player.x,state.player.y);
      smokeCheck("hover-known-square", hero?.x===state.player.x && hero?.y===state.player.y,
        "Pointer over hero selects its logical square");
      const mapRect = map.getBoundingClientRect();
      const unknown = [...state.cells.values()].find(c=> {
        const px=rect.left+left+(c.x+.5)*state.tileSize;
        const py=rect.top+top+(c.y+.5)*tileHeight();
        return c.tile===1469 && px>=mapRect.left && px<mapRect.right &&
          py>=mapRect.top && py<mapRect.bottom;
      });
      if (unknown) {
        const focus = point(unknown.x,unknown.y);
        smokeCheck("hover-unexplored-square", focus?.x===unknown.x && focus?.y===unknown.y,
          "Unexplored hover retains its coordinates instead of selecting the hero");
      }
      if (unknown) {
        point(unknown.x,unknown.y);
        $("engine-dialog").showModal();
        // A top-layer prompt steals hover without any physical pointer move.
        map.dispatchEvent(new MouseEvent("mouseleave"));
        closeEngineDialog();
        render();
        smokeCheck("hover-dialog-close", observed?.x===unknown.x && observed?.y===unknown.y,
          "Closing a modal restores the stationary pointer over unexplored ground");
      }
      const outside = point(state.player.x,state.height);
      smokeCheck("hover-outside-grid", outside===null && state.hover===null,
        "Blank map area below the grid does not fall back to hero cutaway");
      map.dispatchEvent(new MouseEvent("mouseleave"));
      render();
      smokeCheck("hover-map-leave", observed===null,
        "Leaving the map clears cutaway instead of selecting the hero");
      const toolbar = $("actions-button").getBoundingClientRect();
      document.dispatchEvent(new MouseEvent("mousemove", {
        clientX:toolbar.left+toolbar.width/2,clientY:toolbar.top+toolbar.height/2}));
      $("engine-dialog").showModal();
      closeEngineDialog();
      render();
      smokeCheck("hover-toolbar-dialog-close", observed===null,
        "Closing a dialog with the pointer in the toolbar leaves artwork solid");
      const input = state.input;
      try {
        state.input = {...input,targeting:true};
        render();
        smokeCheck("hover-targeting", observed===state.cursor,
          "Active targeting retains its cursor focus outside the map");
      } finally { state.input = input; }
    } finally {
      AtlasTiles.paintMap = painter;
      clearTimeout(hoverTimer);
      state.hover=null;state.mapPointerInside=false;
    }
  }
  function smokeEvent(event) {
    if (!smoke.enabled) return;
    if (smoke.scenario === "room-shape") {
      if (event.type !== "input" || smoke.stage === "shape-loading" || smoke.stage === "complete") return;
      if (!event.command) {
        setTimeout(() => respondInput({action:"key",key:event.kind === "yn" ? "n" : " "}), 50);
        return;
      }
      smoke.stage = "shape-loading";
      const atlas = state.tilesets[0]?.id;
      let attempts = 0;
      const [x,y,w,h] = smoke.roomBounds;
      const roomWalls = () => [...state.cells.values()].filter(c =>
        c.x >= x && c.x < x+w && c.y >= y && c.y < y+h &&
        state.selectedAtlas?.lanternWalls?.tiles?.[c.tile]);
      const terrainReady = () => smoke.terrainTiles?.length
        ? smoke.terrainTiles.every(tile => [...state.cells.values()].some(c =>
            c.x >= x && c.x < x+w && c.y >= y && c.y < y+h && c.tile === tile))
        : roomWalls().length > 0;
      const capture = () => {
        // Restore sends cells separately from atlas loading. Require the actual
        // expected terrain (for wall-free lava/cold fixtures) or mapped walls.
        if (state.selectedAtlas?.id !== atlas || !state.atlas?.complete ||
            !state.waiting || !state.command || !terrainReady()) {
          if (++attempts < 100) { setTimeout(capture, 50); return; }
          diagnostic("complete", false,
            `Room-shape did not become ready: atlas ${state.selectedAtlas?.id}; cells ${state.cells.size}; walls ${roomWalls().length}; command ${state.command}`);
          return;
        }
        const map = $("map-container");
        state.follow = false;
        adjustZoom(Math.min(64, Math.floor(map.clientWidth/(w+6)),
          Math.floor(map.clientHeight/(h+6))) - state.tileSize);
        // Let WebKit finish the resized canvas layout before scrolling. Rects
        // use viewport coordinates and remain correct across offset parents.
        // WebKit can suspend animation frames when this automated window is
        // occluded. A bounded fallback keeps native captures from hanging;
        // normal gameplay still uses its existing animation scheduling.
        let framed = false;
        const captureFrame = () => {
          if (framed) return;
          framed = true;
          const [left,top] = mapPadding();
          const frame = () => {
            const canvasRect = canvas.getBoundingClientRect();
            const mapRect = map.getBoundingClientRect();
            map.scrollLeft += canvasRect.left + left + (x+w/2)*state.tileSize -
              (mapRect.left + map.clientWidth/2);
            map.scrollTop += canvasRect.top + top + (y+h/2)*tileHeight() -
              (mapRect.top + map.clientHeight/2);
            render();
          };
          frame();
          setTimeout(() => {
            frame();
            const mapRect = map.getBoundingClientRect();
            const canvasRect = canvas.getBoundingClientRect();
            const cx = canvasRect.left + left + (x+w/2)*state.tileSize;
            const cy = canvasRect.top + top + (y+h/2)*tileHeight();
            const walls = roomWalls();
            const visible = cx >= mapRect.left && cx < mapRect.right &&
              cy >= mapRect.top && cy < mapRect.bottom;
            smokeHoverFocus();
            smokeCheck("room-shape", state.selectedAtlas?.id === atlas &&
              state.atlas?.complete && terrainReady() && visible,
              `Real engine room at ${smoke.roomBounds}; atlas ${atlas}; tile size ${state.tileSize}; walls ${walls.length}; centered ${visible}`);
            setTimeout(() => {
              smoke.stage = "complete";
              diagnostic("complete", !smoke.failed, "Room-shape native capture complete");
            }, 600);
          }, 500);
        };
        requestAnimationFrame(() => requestAnimationFrame(captureFrame));
        setTimeout(captureFrame, 250);
      };
      capture();
      return;
    }
    if (smoke.scenario === "oracle-dialog") {
      smokeOracleEvent(event);
      return;
    }
    if (smoke.scenario === "court-inspection") {
      smokeCourtEvent(event);
      return;
    }
    if (smoke.scenario === "lantern-gameplay") {
      smokeLanternEvent(event);
      return;
    }
    if (smoke.scenario === "lantern-bars") {
      smokeLanternBarsEvent(event);
      return;
    }
    if (smoke.scenario === "pet-target") {
      smokePetTargetEvent(event);
      return;
    }
    if (smoke.scenario === "prompt-messages") {
      smokePromptEvent(event);
      return;
    }
    if (event.type === "cell") smoke.cells++;
    if (event.type === "inspect" && smoke.stage === "inspectChest" &&
      event.x === smoke.chestCandidate?.x && event.y === smoke.chestCandidate?.y) {
      if (/Beginner supplies/i.test(event.text || "")) {
        smoke.chestPath = smokePathToChest(smoke.chestCandidate);
        smokeCheck("beginner-chest-visible", !!smoke.chestPath,
          `Engine inspection identifies ${event.text}; path ${smoke.chestPath?.length || 0} steps`);
        if (!smoke.chestPath) smokeContinueAfterChest();
        else {
          smoke.stage = "movingToChest";
          setTimeout(() => smokeClickTile(smoke.chestPath[0].x,
            smoke.chestPath[0].y), 900);
        }
      } else smokeInspectNextChest();
      return;
    }
    if (event.type === "inspect" && smoke.stage === "inspect") {
      const after = smokeSnapshot();
      smoke.inspected = !!event.text;
      smokeCheck(
        "hover",
        smoke.inspected &&
          after.turn === smoke.beforeInspect.turn &&
          after.x === smoke.beforeInspect.x &&
          after.y === smoke.beforeInspect.y,
        `Turn ${after.turn} unchanged; ${event.text}`
      );
      smoke.beforeWait = after;
      smoke.stage = "waitPrefix";
      // NetHack 5.0 can refuse an unprefixed wait near a monster.
      setTimeout(() => {
        key("m");
        send({ action: "key", key: "." });
      }, 120);
    }
    if (event.type === "input") {
      if (
        event.direction &&
        ["direction", "directionCancel"].includes(smoke.stage)
      ) {
        smokeCheck(
          "direction-bar",
          !$("engine-dialog").open && !$("direction-bar").hidden,
          "Direction request leaves dungeon visible without a modal dialog"
        );
        if (smoke.stage === "direction") {
          smoke.stage = "directionAnswered";
          setTimeout(() => smokePress("ArrowUp"), 200);
        } else {
          smoke.stage = "directionCancelled";
          setTimeout(() => smokePress("Escape"), 200);
        }
        return;
      }
      diagnostic(
        "input-" + event.kind,
        true,
        event.prompt || "command=" + event.command
      );
      if (event.kind === "key" && event.command) {
        if (smoke.blind && smoke.stage === "start") {
          const bits = Number(stat("condition"));
          smokeCheck("blind-status", !!(bits & 2) &&
            $("conditions").textContent.includes("Blind") &&
            (smoke.deaf ? !!(bits & 16) && $("conditions").textContent.includes("Deaf") : true),
            `Engine condition mask ${bits}; displayed ${$("conditions").textContent}`);
          smokeCheck("blind-perception",
            [...state.cells.values()].filter(cell => cell.char !== " ").length <= 1,
            "Only the hero square is displayed at a blind start");
          smoke.stage = "blindSave";
          setTimeout(() => $("save-button").click(), 100);
          return;
        }
        if (smoke.blind && smoke.stage === "blindRestore") {
          const bits = Number(stat("condition"));
          smokeCheck("blind-restore", !!(bits & 2) &&
            (smoke.deaf ? !!(bits & 16) : true) && state.mode === smoke.mode,
            `Saved conditions and ${smoke.mode} mode survived restore`);
          smoke.stage = "complete";
          setTimeout(() => diagnostic("complete", !smoke.failed,
            "Blind starting conditions passed through native save and restore"), 100);
          return;
        }
        if (smoke.stage === "start") {
          if (smoke.deaf) smokeCheck("deaf-status", !!(Number(stat("condition")) & 16) &&
            $("conditions").textContent.includes("Deaf"), "Engine reports Deaf from birth");
          if (smoke.noStartingPet) smokeCheck("no-starting-pet",
            ![...state.cells.values()].some(cell => cell.pet),
            "No pet appears on the initial engine map");
          smokeCheck("experience-status", state.experience?.level === 1 &&
            state.experience.points === 0 && state.experience.next === 20 &&
            $("experience-value").textContent === "0 / 20 XP" &&
            $("level-value").textContent === "Level 1" &&
            $("experience-progress").getAttribute("aria-valuenow") === "0",
            "Live level-one hero displays 0 / 20 XP and an empty progress bar");
          smoke.stage = "attributes";
          if (["beginner", "explore", "pauper"].includes(smoke.mode)) {
            $("help-button").click();
            if (smoke.mode === "explore") $("explore-help").scrollIntoView({ block: "center" });
            if (smoke.mode === "explore") smokeCheck("explore-help",
              state.mode === "explore" && !$("explore-help").hidden &&
              $("help-dialog").open && $("explore-help").getBoundingClientRect().height > 0 &&
              $("adventure-mode").textContent.includes("non-scoring") &&
              state.messages.some((text) => text.includes("non-scoring explore")) &&
              !state.commands.some((command) => command.name === "wizwish"),
              "Explore guide and badge match native discovery mode without wizard commands");
            else if (smoke.mode === "pauper") smokeCheck("pauper-help",
              state.mode === "pauper" &&
              $("adventure-mode").textContent === "Pauper start" &&
              $("help-dialog").open && !$("pauper-help").hidden &&
              $("pauper-help").textContent.includes("without items"),
              "Pauper badge and in-game starting rules are visible");
            else smokeCheck("beginner-help",
              state.mode === "beginner" &&
              $("adventure-mode").textContent === "Beginner start" &&
              $("help-dialog").open && !$('beginner-help').hidden &&
              $("beginner-help").textContent.includes("same level"),
              "Beginner badge and in-game supply instructions are visible");
            setTimeout(() => {
              $("help-dialog").close();
              key(24);
            }, 900);
          } else setTimeout(() => key(24), 100);
        } else if (smoke.stage === "attributesClosed") {
          smokeCheck(
            "alignment",
            stat("alignment").toLowerCase() === "neutral",
            "Creation form selected Neutral; engine reports " +
              stat("alignment")
          );
          smoke.stage = "awaitingAtlas";
          const deadline = Date.now() + 3000;
          const checkAtlas = () => {
            const loaded =
              !!state.atlas?.complete &&
              state.atlas.naturalWidth > 0 &&
              !state.ascii;
            if (!loaded && Date.now() < deadline) {
              setTimeout(checkAtlas, 50);
              return;
            }
            smokeCheck(
              "render",
              smoke.cells > 0 && canvas.width > 0 && loaded,
              `${smoke.cells} live engine cells; atlas ${
                loaded ? state.selectedAtlas.id + " loaded" : "missing"
              }; HP ${$("hp-value").textContent}`
            );
            const stairAction = $("context-actions").querySelector('[data-action="up"]');
            const contextual = [...$("context-actions").querySelectorAll("button")];
            smokeCheck(
              "context-underfoot",
              !!stairAction && !stairAction.disabled &&
                new Set(contextual.map((button) => button.dataset.action)).size === contextual.length &&
                (smoke.mode !== "beginner" ||
                  !$("context-actions").querySelector('[data-action="loot"]')) &&
                !document.querySelector('.quick-actions [data-command=">"]'),
              "Starting stairs remain actionable and distinct from the nearby supply chest"
            );
            smoke.stage = "actionPicker";
            setTimeout(() => {
              const before = smokeSnapshot();
              $("actions-button").click();
              $("action-filter").value = "s";
              $("action-filter").dispatchEvent(
                new Event("input", { bubbles: true })
              );
              const names = [
                ...$("action-results").querySelectorAll("button"),
              ].map((row) => row.dataset.action);
              smokeCheck(
                "actions-prefix",
                names.includes("sit") &&
                  names.includes("search") &&
                  names[0]?.startsWith("s"),
                names.join(", ")
              );
              $("action-filter").value = "kick";
              $("action-filter").dispatchEvent(
                new Event("input", { bubbles: true })
              );
              const rows = [...$("action-results").querySelectorAll("button")];
              smokeCheck(
                "actions-filter",
                $("actions-dialog").open &&
                  rows.length === 1 &&
                  rows[0].dataset.action === "kick" &&
                  rows[0].textContent.includes("Ctrl+D") &&
                  smokeSnapshot().turn === before.turn,
                "Kick found with Ctrl+D; browsing spends no turn"
              );
              setTimeout(() => {
                $("actions-dialog").close();
                smokeCheck(
                  "actions-cancel",
                  smokeSnapshot().turn === before.turn && state.waiting,
                  "Closing the picker leaves engine ready without spending a turn"
                );
                openActions();
                $("action-filter").value = "inventory";
                $("action-filter").dispatchEvent(
                  new Event("input", { bubbles: true })
                );
                smoke.stage = "inventory";
                $("action-results")
                  .querySelector('[data-action="inventory"]')
                  .click();
              }, 250);
            }, 200);
          };
          checkAtlas();
        } else if (smoke.stage === "inventory" && smoke.mode === "pauper") {
          smokeCheck("inventory", state.mode === "pauper",
            "Pauper inventory command returned to gameplay");
          smokeCheck("pauper-inventory",
            state.messages.some((text) => text.includes("Not carrying anything.")),
            "The live engine reports an empty starting inventory");
          smoke.stage = "inventoryClosed";
          smokeContinueAfterChest();
        } else if (smoke.stage === "inventoryClosed") {
          if (smoke.mode === "beginner") smokeFindChest();
          else smokeContinueAfterChest();
        } else if (smoke.stage === "movingToChest") {
          const expected = smoke.chestPath.shift();
          if (state.player.x !== expected?.x || state.player.y !== expected?.y) {
            smokeCheck("beginner-chest", false,
              `Movement toward supply chest stopped at ${state.player.x},${state.player.y}`);
            smokeContinueAfterChest();
          } else if (smoke.chestPath.length) {
            const next = smoke.chestPath[0];
            setTimeout(() => smokeClickTile(next.x, next.y), 100);
          } else {
            const loot = $("context-actions").querySelector('[data-action="loot"]');
            const stairs = $("context-actions").querySelector('[data-action="up"]');
            smokeCheck("beginner-chest", !!loot && !loot.disabled && !stairs,
              "On the named chest: Loot container is available; starting stairs are elsewhere");
            if (loot && !loot.disabled) {
              smoke.stage = "lootAction";
              setTimeout(() => loot.click(), 900);
            } else smokeContinueAfterChest();
          }
        } else if (smoke.stage === "lootClosed") {
          smokeContinueAfterChest();
        } else if (smoke.stage === "readClosed") {
          smokeCheck("read-cancel", smokeSnapshot().turn === smoke.beforeRead.turn,
            "Canceling item selection preserves the turn");
          smokeMove();
        } else if (smoke.stage === "moving") {
          const after = smokeSnapshot();
          smokeCheck(
            "arrow-movement",
            after.x === smoke.target.x &&
              after.y === smoke.target.y &&
              after.turn > smoke.beforeMove.turn,
            `${smoke.target.key}: (${smoke.beforeMove.x},${smoke.beforeMove.y}) turn ${smoke.beforeMove.turn} → (${after.x},${after.y}) turn ${after.turn}`
          );
          smokeMove("mouse");
        } else if (smoke.stage === "mouseMoving") {
          const after = smokeSnapshot();
          smokeCheck(
            "mouse-movement",
            after.x === smoke.target.x &&
              after.y === smoke.target.y &&
              after.turn > smoke.beforeMove.turn,
            `Mouse: (${smoke.beforeMove.x},${smoke.beforeMove.y}) → (${after.x},${after.y})`
          );
          smokeClickTile(after.x > 40 ? after.x - 3 : after.x + 3, after.y);
          smokeCheck(
            "mouse-distance",
            state.waiting,
            "Distant clicks do not send movement or travel commands"
          );
          smoke.stage = "inspect";
          smoke.beforeInspect = after;
          inspectCell(after.x, after.y);
        } else if (smoke.stage === "waitPrefix") {
          // The movement prefix emits another input request before the rest action.
          smoke.stage = "wait";
        } else if (smoke.stage === "wait") {
          const after = smokeSnapshot();
          smokeCheck(
            "wait",
            after.turn === smoke.beforeWait.turn + 1,
            `Wait advanced exactly one turn: ${smoke.beforeWait.turn} → ${after.turn}`
          );
          smoke.stage = "direction";
          setTimeout(() => key("o"), 100);
        } else if (smoke.stage === "directionAnswered") {
          smokeCheck(
            "direction-arrow",
            $("direction-bar").hidden && !$("engine-dialog").open,
            "Arrow answered the direction request and returned to gameplay"
          );
          smoke.beforeDirectionCancel = smokeSnapshot();
          smoke.stage = "directionCancel";
          setTimeout(() => key("o"), 100);
        } else if (smoke.stage === "directionCancelled") {
          smokeCheck(
            "direction-cancel",
            smokeSnapshot().turn === smoke.beforeDirectionCancel.turn &&
              $("direction-bar").hidden,
            "Escape cancels direction without consuming a turn"
          );
          smoke.stage = "saveValidation";
          smoke.beforeSaveValidation = smokeSnapshot();
          setTimeout(() => chooseAction(state.commands.find(command => command.name === "save")), 100);
        } else if (smoke.stage === "saveCancelled") {
          smokeCheck("yn-default-enter", smokeSnapshot().turn === smoke.beforeSaveValidation.turn,
            "Enter on the focused No canceled the real save prompt without advancing time");
          smoke.saved = smokeSnapshot();
          smoke.stage = "save";
          setTimeout(() => chooseAction(state.commands.find(command => command.name === "save")), 100);
        } else if (smoke.stage === "restore") {
          const restored = smokeSnapshot(),
            saved = smoke.saved;
          smokeCheck(
            "restore",
            restored.turn === saved.turn &&
              restored.x === saved.x &&
              restored.y === saved.y && state.mode === smoke.mode,
            `Saved (${saved.x},${saved.y}) turn ${saved.turn}; restored (${restored.x},${restored.y}) turn ${restored.turn}; mode ${state.mode}`
          );
          smoke.stage = "complete";
          setTimeout(
            () =>
              diagnostic(
                "complete",
                !smoke.failed && smoke.inspected && smoke.cells > 0,
                "Native start, render, inventory, arrow movement, turn-free hover, wait, invalid answer recovery, save and exact restore checked"
              ),
            300
          );
        }
      } else if (event.kind === "menu" || event.kind === "text") {
        if (smoke.stage === "lootClosed") {
          setTimeout(() => event.kind === "menu" ? cancelInput() :
            respondInput({ action: "key", key: " " }), 100);
          return;
        }
        if (smoke.stage === "lootAction" && event.kind === "menu") {
          const take = (event.items || []).find((item) =>
            item.selectable && /take/i.test(item.text));
          smokeCheck("beginner-loot-action", !!take,
            (event.items || []).map((item) => item.text).join("; "));
          if (take) {
            smoke.stage = "lootContents";
            setTimeout(() => respondInput({ action: "menu",
              selections: [{ id: take.id, count: -1 }] }), 100);
          } else {
            smoke.stage = "lootClosed";
            setTimeout(cancelInput, 100);
          }
          return;
        }
        if (smoke.stage === "lootContents" && event.kind === "menu") {
          const allTypes = (event.items || []).find((item) =>
            item.selectable && /all types/i.test(item.text));
          if (allTypes) {
            setTimeout(() => respondInput({ action: "menu",
              selections: [{ id: allTypes.id, count: -1 }] }), 100);
            return;
          }
          const items = (event.items || []).map((item) => item.text).join("; ");
          smokeCheck("beginner-chest-contents",
            /magic whistle/i.test(items) && /food ration/i.test(items) &&
              /potion of healing/i.test(items) && /gold/i.test(items),
            items);
          smoke.stage = "lootClosed";
          setTimeout(cancelInput, 100);
          return;
        }
        if (smoke.stage === "readSelection") {
          const items = (event.items || []).filter((item) =>
            item.selectable && item.key !== "*" && item.key !== "?");
          smokeCheck("read-selection",
            event.kind === "menu" && /read/i.test(event.prompt || "") &&
              items.length > 0 && items.every((item) => item.text.length > 1) &&
              $("dialog-options").querySelectorAll(".menu-row").length >= items.length,
            items.map((item) => item.text).join("; "));
          smoke.stage = "readClosed";
          setTimeout(cancelInput, 250);
          return;
        }
        if (smoke.stage === "attributes") {
          const text = (
            event.lines || (event.items || []).map((item) => item.text)
          ).join(" ");
          smokeCheck(
            "sex",
            text.includes(" " + smoke.gender + " human Wizard"),
            text
          );
          smoke.stage = "attributesClosed";
        }
        if (smoke.stage === "inventory") {
          if (smoke.nudist) smokeCheck("nudist-inventory",
            !(event.items || []).some((item) => item.text === "Armor" || /being worn/.test(item.text)),
            "Live starting inventory contains no armor");
          if (smoke.mode === "explore") smokeCheck("explore-inventory",
            event.items?.some((item) => /wand of wishing.*\(0:3\)/.test(item.text)),
            (event.items || []).map((item) => item.text).join("; "));
          smokeCheck(
            "inventory",
            state.mode === smoke.mode,
            `${event.items?.length || event.lines?.length || 0} role inventory entries displayed; mode ${state.mode}`
          );
          smoke.stage = "inventoryClosed";
        }
        const decline = /tutorial/i.test(event.prompt || "")
          ? (event.items || []).find((i) => i.key === "n")
          : undefined;
        setTimeout(
          () =>
            respondInput(
              event.kind === "menu"
                ? {
                    action: "menu",
                    selections: decline ? [{ id: decline.id, count: -1 }] : [],
                  }
                : { action: "key", key: " " }
            ),
          100
        );
      } else if (event.kind === "yn") {
        if (smoke.mode === "explore" && smoke.stage === "restore") {
          smokeCheck("explore-restore-choice", event.prompt === "Do you want to keep the save file?",
            "Native Explore restoration offers to retain the saved snapshot");
          setTimeout(() => respondInput({ action: "key", key: "n" }), 100);
          return;
        }
        if (smoke.stage === "lootAction") {
          setTimeout(() => respondInput({ action: "key", key: "y" }), 100);
          return;
        }
        if (smoke.stage === "lootContents" || smoke.stage === "lootClosed") {
          smoke.stage = "lootClosed";
          setTimeout(() => respondInput({ action: "key", key: "n" }), 100);
          return;
        }
        if (smoke.stage === "saveValidation") {
          setTimeout(() => {
            smokeCheck("yn-default-focus", event.default === "n" &&
              document.activeElement?.dataset.answer === "n" && document.activeElement.textContent.includes("↵"),
              "The actual engine default No receives both keyboard focus and the Enter marker");
            // Keep the real prompt open long enough for its native snapshot.
            setTimeout(() => {
              document.dispatchEvent(
                new KeyboardEvent("keydown", {
                  key: "x",
                  bubbles: true,
                  cancelable: true,
                })
              );
              smokeCheck(
                "yn-invalid",
                state.input === event && $("engine-dialog").open,
                "Invalid x leaves the real yes/no prompt open and awaiting a valid answer"
              );
              smoke.stage = "saveCancelled";
              document.dispatchEvent(
                new KeyboardEvent("keydown", {
                  key: "Enter",
                  bubbles: true,
                  cancelable: true,
                })
              );
            }, 250);
          }, 100);
        } else if (smoke.stage === "save") setTimeout(() => {
          const yes = $("dialog-options").querySelector('[data-answer="y"]');
          yes.focus();
          smokeCheck("yn-focused-enter", document.activeElement === yes && yes.textContent.includes("↵"),
            "Changing focus to Yes moves the Enter marker; Enter will save through the real engine");
          document.dispatchEvent(new KeyboardEvent("keydown", {key:"Enter",bubbles:true,cancelable:true}));
        },100);
        else setTimeout(() => respondInput({ action: "key", key: "y" }), 100);
      } else if (event.kind === "key") {
        setTimeout(() => {
          state.waiting = true;
          key(" ");
        }, 100);
      }
    }
    if (
      event.type === "exit" &&
      event.code !== undefined &&
      smoke.stage === "blindSave"
    ) {
      smokeCheck("blind-save", event.hasSave === true && event.code === 0,
        "Native save completed for blind character");
      smoke.stage = "blindRestore";
      setTimeout(() => {
        const picker = $("saved-game-select");
        const index = [...picker.options].findIndex(option =>
          option.value === "AtlasSmoke" && option.dataset.mode === smoke.mode);
        smokeCheck("save-picker", index >= 0, "Blind save is listed by its mode");
        if (index >= 0) {
          picker.selectedIndex = index;
          $("load-button").click();
        }
      }, 250);
    }
    if (
      event.type === "exit" &&
      event.code !== undefined &&
      smoke.stage === "save"
    ) {
      smokeCheck(
        "save",
        event.hasSave === true && event.code === 0,
        "Engine exited successfully after native save"
      );
      smoke.stage = "restore";
      setTimeout(() => {
        const opposite = smoke.mode === "beginner" ? "standard" : "beginner";
        $("player-mode").value = opposite;
        updateModeHelp();
        const picker = $("saved-game-select");
        const options = [...picker.options];
        const index = options.findIndex((option) =>
          option.value === "AtlasSmoke" && option.dataset.mode === smoke.mode);
        if (index >= 0) picker.selectedIndex = index;
        const hasOtherMode = options.some((option) =>
          option.value === "AtlasSmoke" && option.dataset.mode === opposite);
        smokeCheck("save-picker",
          index >= 0 && !$('load-button').disabled &&
            $("player-mode").value === opposite &&
            (smoke.mode === "standard" || hasOtherMode),
          `Selected AtlasSmoke · ${smoke.mode} from ${options.map((option) =>
            option.textContent).join("; ")}; creation selector is ${opposite}`);
        if (index >= 0 && !$('load-button').disabled) $("load-button").click();
      }, 250);
    }
  }
  function smokeOracleEvent(event) {
    if (event.type === "error") {
      smoke.failed = true;
      diagnostic("complete", false, event.text || "Oracle fixture failed");
      return;
    }
    if (event.type !== "input" || smoke.stage === "complete") return;
    const later = (fn) => setTimeout(fn, 800);
    const press = (value) => document.dispatchEvent(new KeyboardEvent("keydown",
      {key:value, bubbles:true, cancelable:true}));
    if (smoke.stage === "prompt-start" && !event.command) {
      later(() => respondInput({action:"key", key:event.kind === "yn" ? "n" : " "}));
      return;
    }
    if (event.command) {
      const gold = Number(stat("gold").replace(/^.*?:\s*/, ""));
      const turn = smokeSnapshot().turn;
      if (smoke.oracleCase !== undefined) {
        const paid = smoke.oracleCase === 2 ? 50 : smoke.oracleCase === 3 ? smoke.oracleMajorCost : 0;
        // A fast hero can take another action within the same displayed turn.
        const timeOK = paid ? turn >= smoke.oracleTurn && turn <= smoke.oracleTurn + 1
          : turn === smoke.oracleTurn;
        smokeCheck("oracle-result-" + smoke.oracleCase,
          gold === smoke.oracleGold - paid && timeOK &&
          !$("engine-dialog").open &&
          (smoke.oracleCase !== 2 || $("messages").textContent.includes("True to her word, the Oracle")) &&
          (smoke.oracleCase !== 3 || smoke.oracleTextSeen),
          `Consultation ${smoke.oracleCase}: gold ${smoke.oracleGold} to ${gold}, turn ${smoke.oracleTurn} to ${turn}; map input restored`);
        smoke.oracleCase++;
      } else smoke.oracleCase = 0;
      if (smoke.oracleCase === 4) {
        smoke.stage = "complete";
        diagnostic("complete", !smoke.failed, "Oracle cancellation, minor hint and major text dialog checked through live controls");
        return;
      }
      smoke.oracleGold = gold;
      smoke.oracleTurn = turn;
      smoke.stage = "oracle-chat";
      later(() => chooseAction({name:"chat"}));
    } else if (event.direction) {
      smokeCheck("oracle-direction", !$("engine-dialog").open, "Chat uses the ordinary direction bar");
      later(() => press("b")); // Fixture hero northeast of the Oracle.
    } else if (event.kind === "yn" && /minor consultation/.test(event.prompt)) {
      smokeCheck("oracle-minor-prompt", $("engine-dialog").open &&
        $("dialog-title").textContent === event.prompt && event.prompt.includes("50") &&
        ["y","n","q"].every(answer => $("dialog-options").querySelector(`[data-answer="${answer}"]`)),
        "Minor consultation shows its cost and Yes, No, Cancel choices");
      if (smoke.oracleCase === 0) later(() => press("Escape"));
      else later(() => $("dialog-options").querySelector(`[data-answer="${smoke.oracleCase === 2 ? "y" : "n"}"]`).click());
    } else if (event.kind === "yn" && /major one/.test(event.prompt)) {
      smoke.oracleMajorCost = Number(event.prompt.match(/\((\d+)/)?.[1]);
      smokeCheck("oracle-major-prompt", $("engine-dialog").open &&
        $("dialog-title").textContent === event.prompt && smoke.oracleMajorCost > 50,
        "Declining minor consultation displays the engine's major consultation cost");
      if (smoke.oracleCase === 1) later(() => press("Escape"));
      else later(() => $("dialog-options").querySelector('[data-answer="y"]').click());
    } else if (event.kind === "text") {
      smoke.oracleTextSeen = true;
      smokeCheck("oracle-reading", smoke.oracleCase === 3 && $("engine-dialog").open &&
        $("dialog-text").textContent === event.lines.join("\n") &&
        event.lines.join(" ").includes("The Oracle meditates") && event.lines.length > 3 &&
        !$("dialog-submit").hidden,
        "Complete major consultation text appears in the dialog with Continue available");
      later(() => $("dialog-submit").click());
    } else if (event.kind === "key") later(() => press(" "));
    else diagnostic("complete", false, "Unexpected Oracle input: " + JSON.stringify(event));
  }

  function smokeCourtEvent(event) {
    if (event.type === "error") {
      diagnostic("complete", false, event.text || "Court inspection failed");
    } else if (event.type === "input" && smoke.stage === "prompt-start") {
      if (event.kind === "yn") {
        setTimeout(() => respondInput({action:"key",key:"n"}), 100);
      } else if (event.command) {
        smoke.stage = "court-loading";
        chooseAtlas(state.tilesets[0]?.id || "lantern-modern").then(() => {
          smoke.courtTurn = smokeSnapshot().turn;
          smoke.stage = "court-inspect";
          inspectCell(13, 7);
        });
      }
    } else if (event.type === "inspect" && smoke.stage === "court-inspect") {
      smokeCheck("court-beneath", event.beneath?.name === "Throne" &&
        event.beneath.remembered === false &&
        $("inspector-details").textContent.includes("BeneathThrone") &&
        smokeSnapshot().turn === smoke.courtTurn,
        "Known throne appears beneath its occupant in inspection without spending a turn");
      smoke.stage = "court-clearing";
      setTimeout(() => inspectCell(14, 7), 700);
    } else if (event.type === "inspect" && smoke.stage === "court-clearing") {
      smokeCheck("court-clear", !event.beneath &&
        !$("inspector-details").textContent.includes("Throne") &&
        smokeSnapshot().turn === smoke.courtTurn,
        "Moving inspection to a different feature clears the throne detail without a turn");
      smoke.stage = "complete";
      diagnostic("complete", !smoke.failed, "Court inspection passed");
    }
  }

  // Restored real-engine fixture, enabled only by the native self-test flag.
  function smokeLanternEvent(event) {
    if (event.type === "error") {
      diagnostic("complete", false, event.text || "Lantern fixture failed");
      return;
    }
    if (event.type !== "input" || smoke.stage === "complete") return;
    if (event.kind === "yn") {
      setTimeout(() => respondInput({ action: "key", key: "n" }), 100);
    } else if (event.kind === "text" || event.kind === "key" && !event.command) {
      setTimeout(() => respondInput({ action: "key", key: " " }), 100);
    } else if (event.kind === "key" && event.command) {
      if (smoke.stage === "lantern-moving") {
        const after = smokeSnapshot();
        smokeCheck("lantern-move", after.x === 13 && after.y === 5 &&
          after.turn === smoke.lanternStart.turn + 1,
          `ArrowRight moved to (${after.x},${after.y}), turn ${smoke.lanternStart.turn} to ${after.turn}`);
        smoke.stage = "complete";
        diagnostic("complete", !smoke.failed,
          "Restored engine cells rendered with selected atlas; ordinary movement stays one square per turn");
        return;
      }
      if (smoke.stage === "lantern-loading") return;
      smoke.stage = "lantern-loading";
      const fixtureAtlas = state.tilesets[0]?.id || "lantern";
      chooseAtlas(fixtureAtlas);
      let attempts = 0;
      const ready = () => {
        const loaded = state.selectedAtlas?.id === fixtureAtlas &&
          state.selectedAtlas?.tileWidth === 64 && state.atlas?.complete;
        if (!loaded && ++attempts < 100) { setTimeout(ready, 50); return; }
        smoke.lanternStart = smokeSnapshot();
        const cell = (x, y) => state.cells.get(`${x},${y}`);
        const actual = { atlas: state.selectedAtlas?.id, size: state.tileSize,
          hero: cell(12,5), chest: cell(14,5), eye: cell(13,7),
          northDoor: cell(13,3), sideDoor: cell(16,6), unknown: cell(70,19) };
        smokeCheck("lantern-fixture", loaded && state.tileSize === 64 &&
          smoke.lanternStart.x === 12 && smoke.lanternStart.y === 5 &&
          actual.hero?.groundTile === 1291 && actual.chest?.groundTile === 1291 &&
          actual.eye?.groundTile === 1291 && actual.northDoor?.tile === 1288 &&
          actual.sideDoor?.tile === 1287 && actual.unknown?.groundTile === undefined,
          JSON.stringify(actual));
        smoke.stage = "lantern-moving";
        // Let the renderer and native diagnostic screenshot capture this state.
        setTimeout(() => smokePress("ArrowRight"), 1000);
      };
      setTimeout(ready, 100);
    }
  }
  function smokeLanternBarsEvent(event) {
    if (event.type === "error") {
      diagnostic("complete", false, event.text || "Bars fixture failed");
      return;
    }
    if (event.type !== "input" || smoke.stage === "complete") return;
    if (event.kind === "yn") {
      setTimeout(() => respondInput({ action:"key", key:"n" }), 100);
    } else if (event.kind === "text" || event.kind === "key" && !event.command) {
      setTimeout(() => respondInput({ action:"key", key:" " }), 100);
    } else if (event.kind === "key" && event.command) {
      if (smoke.stage === "bars-blocking") {
        const after = smokeSnapshot();
        smokeCheck("lantern-bars-blocked", after.x === smoke.barsStart.x &&
          after.y === smoke.barsStart.y && after.turn === smoke.barsStart.turn,
          `ArrowDown into iron bars leaves (${after.x},${after.y}) and turn ${after.turn} unchanged`);
        smoke.stage = "complete";
        diagnostic("complete", !smoke.failed, "Actual iron bars render over perceived floor and block ordinary movement");
        return;
      }
      if (smoke.stage === "bars-loading") return;
      smoke.stage = "bars-loading";
      const fixtureAtlas = state.tilesets[0]?.id || "lantern";
      chooseAtlas(fixtureAtlas);
      let attempts = 0;
      const ready = () => {
        const loaded = state.selectedAtlas?.id === fixtureAtlas &&
          state.selectedAtlas?.tileWidth === 64 && state.selectedAtlas?.lanternWalls?.bars &&
          state.atlas?.complete;
        if (!loaded && ++attempts < 100) { setTimeout(ready, 50); return; }
        smoke.barsStart = smokeSnapshot();
        const locations = [[14,3],[18,6],[14,9],[10,6],[14,6]];
        const bars = locations.map(([x,y]) => state.cells.get(`${x},${y}`));
        smokeCheck("lantern-bars-fixture", !!loaded && state.tileSize === 64 &&
          smoke.barsStart.x === 14 && smoke.barsStart.y === 5 &&
          bars.every(cell => cell?.tile === 1289 && cell.groundTile === 1291) &&
          state.cells.get("70,19")?.groundTile === undefined,
          JSON.stringify({atlas:state.selectedAtlas?.id, hero:smoke.barsStart, bars}));
        smoke.stage = "bars-blocking";
        setTimeout(() => smokePress("ArrowDown"), 1000);
      };
      setTimeout(ready, 100);
    }
  }
  // Isolated saved-game fixture uses real scroll, potion and spellbook effects.
  // This checks visible text before responding, rather than replaying messages.
  function smokePromptEvent(event) {
    if (event.type === "error") {
      smoke.failed = true;
      diagnostic("complete", false, event.text || "Fixture launch failed");
      return;
    }
    const cases = [
      { marker: "PromptScroll", key: "r", phase: "prompt-scroll", effect: /maniacal laughter/ },
      { marker: "PromptPotion", key: "q", phase: "prompt-potion", effect: /tastes like/ },
      { marker: "PromptBook", key: "r", phase: "prompt-book", effect: /crumbles to dust/ },
    ];
    if (event.type !== "input") return;
    if (event.kind === "key" && event.command) {
      if (smoke.stage === "prompt-answered") {
        smoke.promptIndex++;
        smoke.promptAttempts = 0;
      }
      if (smoke.promptIndex === cases.length) {
        smoke.stage = "complete";
        diagnostic("complete", !smoke.failed,
          "Live effect messages visible before naming scroll, potion and spellbook; submit, Escape and empty name checked");
        return;
      }
      if (++smoke.promptAttempts > 30) {
        smoke.failed = true;
        diagnostic("complete", false, "Spellbook did not reach a naming prompt");
        return;
      }
      smoke.stage = "prompt-select";
      setTimeout(() => key(cases[smoke.promptIndex].key), 100);
    } else if (event.kind === "menu") {
      if (smoke.stage === "prompt-select") {
        const row = [...$("dialog-options").querySelectorAll(".menu-row")]
          .find((item) => item.textContent.includes(cases[smoke.promptIndex].marker));
        smokeCheck("prompt-context-reset",
          !!row && $("dialog-context").hidden,
          "New action selection does not repeat effects from a previous action");
        smoke.stage = "prompt-effect";
        if (row) setTimeout(() => row.click(), 100);
        else diagnostic("complete", false, "Missing fixture item");
      } else setTimeout(cancelInput, 100); // teleport instructions, if shown
    } else if (event.kind === "line" && smoke.stage === "prompt-effect") {
      const current = cases[smoke.promptIndex];
      const text = $("dialog-messages").textContent;
      smokeCheck(current.phase,
        event.prompt.startsWith("Call ") && $("engine-dialog").open &&
          !$("dialog-context").hidden && current.effect.test(text) &&
          !/You can move again/.test(text) && $("dialog-input").value === "",
        `Before answering ${event.prompt} ${text}`);
      smoke.stage = "prompt-answered";
      setTimeout(() => {
        if (smoke.promptIndex === 1) cancelInput();
        else {
          $("dialog-input").value = smoke.promptIndex === 0 ? "startling sound" : "";
          $("dialog-form").requestSubmit();
        }
      }, 900);
    } else if (event.kind === "yn") {
      setTimeout(() => respondInput({ action: "key", key: "n" }), 100);
    } else if (event.kind === "key") {
      setTimeout(() => event.targeting
        ? respondInput({ action: "key", key: "\x1b" }) : key(" "), 100);
    } else if (event.kind === "text") {
      setTimeout(() => respondInput({ action: "key", key: " " }), 100);
    }
  }
  function smokePetTargetEvent(event) {
    const begin = () => {
      const button = $("context-actions").querySelector('[data-action="name"]');
      if (!button || button.disabled) {
        diagnostic("complete", false, "Missing Name pet action");
        return;
      }
      smoke.stage = "pet-menu";
      setTimeout(() => button.click(), 100);
    };
    if (event.type === "error") {
      diagnostic("complete", false, event.text || "Fixture launch failed");
    } else if (event.type === "inspect" && smoke.stage === "pet-inspect") {
      smokeCheck(smoke.petStep === 0 ? "pet-name-click" : "pet-name-keyboard",
        event.text.includes(smoke.petStep === 0 ? "Mochi" : "Juniper"), event.text);
      smoke.petStep++;
      begin();
    } else if (event.type === "inspect" && smoke.stage === "pet-cancel-inspect") {
      smokeCheck("pet-target-cancel", event.text.includes("Juniper"), event.text);
      smoke.stage = "complete";
      diagnostic("complete", !smoke.failed, "Mouse and keyboard rename the kitten; Escape preserves its name, hero position and turn");
    } else if (event.type === "input") {
      if (event.command) {
        if (smoke.stage === "prompt-start") {
          smoke.pet = [...state.cells.values()].find((cell) => cell.pet);
          if (!smoke.pet) {
            diagnostic("complete", false, "Fixture kitten not visible");
            return;
          }
          smoke.petStart = smokeSnapshot();
          smoke.petStep = 0;
          begin();
        } else if (smoke.stage === "pet-answered" || smoke.stage === "pet-cancelled") {
          const now = smokeSnapshot();
          smokeCheck("pet-no-turn", JSON.stringify(now) === JSON.stringify(smoke.petStart),
            "Naming/selection preserves the hero position and turn");
          smoke.stage = smoke.stage === "pet-cancelled" ? "pet-cancel-inspect" : "pet-inspect";
          send({ action: "inspect", x: smoke.pet.x, y: smoke.pet.y });
        }
      } else if (event.kind === "menu") {
        if (smoke.stage === "pet-menu") {
          const row = [...$("dialog-options").querySelectorAll(".menu-row")]
            .find((item) => item.textContent.includes("a monster"));
          if (!row) {
            diagnostic("complete", false, "Missing monster naming choice");
            return;
          }
          smoke.stage = "pet-target";
          setTimeout(() => row.click(), 100);
        } else setTimeout(cancelInput, 100); // first-use location-selection instructions
      } else if (event.targeting) {
        smokeCheck("pet-target-visible", !$("engine-dialog").open && !$("target-bar").hidden &&
          document.activeElement === canvas, `Targeting keeps the map visible and focused; bindings ${event.directionKeys}`);
        if (smoke.petStep === 0) {
          setTimeout(() => smokeClickTile(smoke.pet.x, smoke.pet.y), 300);
        } else if (smoke.petStep === 2) {
          smoke.stage = "pet-cancelled";
          setTimeout(() => smokePress("Escape"), 100);
        } else {
          const dx = Math.sign(smoke.pet.x - state.cursor.x);
          const dy = Math.sign(smoke.pet.y - state.cursor.y);
          if (!dx && !dy) {
            // Let the canvas paint before the native snapshot is requested.
            setTimeout(() => smokeCheck("pet-target-keyboard", state.player.x === smoke.petStart.x &&
              state.player.y === smoke.petStart.y && state.cells.get(`${state.cursor.x},${state.cursor.y}`)?.pet,
              "Arrow keys moved the selection to the kitten while the hero stayed in place"), 300);
            setTimeout(() => smokePress("Enter"), 900);
          } else {
            const arrow = [["Home", "ArrowUp", "PageUp"],
              ["ArrowLeft", null, "ArrowRight"], ["End", "ArrowDown", "PageDown"]][dy + 1][dx + 1];
            setTimeout(() => smokePress(arrow), 100);
          }
        }
      } else if (event.kind === "line") {
        smokeCheck("pet-name-prompt", /kitten|Mochi/.test(event.prompt), event.prompt);
        smoke.stage = "pet-answered";
        setTimeout(() => {
          $("dialog-input").value = smoke.petStep === 0 ? "Mochi" : "Juniper";
          $("dialog-form").requestSubmit();
        }, 900);
      } else if (event.kind === "yn" && smoke.stage === "prompt-start") {
        setTimeout(() => respondInput({ action: "key", key: "n" }), 100);
      } else if (event.kind === "key") setTimeout(() => key(" "), 100);
      else diagnostic("complete", false, `Unexpected test prompt: ${event.kind} ${event.prompt || ""}`);
    }
  }
  const palette = [
    "#59685e",
    "#c87465",
    "#88a878",
    "#cba86a",
    "#7398b5",
    "#aa82b1",
    "#7bb9b5",
    "#c4cbb6",
    "#777e76",
    "#e09983",
    "#a3c990",
    "#f1d08c",
    "#93b8df",
    "#cb9cd4",
    "#9fdfd2",
    "#ebe9cc",
  ];
  function send(data) {
    if (native) window.webkit.messageHandlers.nethack.postMessage(data);
    else if (preview) previewAction(data);
    else toast("Open Atlas for NetHack on macOS to play.");
  }
  function toast(text) {
    $("toast").textContent = text;
    $("toast").classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 4000);
  }
  function setStatus(text) {
    $("status-message").textContent = text;
  }
  function key(key, commandOnly = false) {
    if (!state.active || !state.waiting || (commandOnly && !state.command))
      return;
    state.waiting = false;
    send({ action: "key", key });
  }
  function setActive(active) {
    state.active = active;
    document
      .querySelectorAll(
        "[data-command],#save-button,#inventory-button,#actions-button,.context-action"
      )
      .forEach((el) => (el.disabled = !active));
    $("engine-state").textContent = active ? "Your turn" : "Ready when you are";
    $("journey-label").textContent = active
      ? "Your adventure is unfolding"
      : "An adventure awaits";
  }
  function setAdventureMode(mode) {
    state.mode = ["beginner", "explore", "pauper"].includes(mode) ? mode : "standard";
    const badge = $("adventure-mode");
    badge.textContent = state.playtest ? `Playtest · ${state.playtest.mode}` : state.mode === "explore" ? "Explore · non-scoring" :
      state.mode === "beginner" ? "Beginner start" : state.mode === "pauper" ? "Pauper start" : "Standard start";
    badge.classList.toggle("beginner", state.mode === "beginner");
    badge.hidden = false;
    $("beginner-help").hidden = state.mode !== "beginner";
    $("explore-help").hidden = state.mode !== "explore";
    $("pauper-help").hidden = state.mode !== "pauper";
  }
  function showSavedGames(savedGames) {
    const select = $("saved-game-select");
    select.replaceChildren();
    for (const save of savedGames) {
      const name = typeof save === "string" ? save : save.name;
      const mode = typeof save === "string" ? "standard" : save.mode;
      if (!name) continue;
      const option = document.createElement("option");
      option.value = name;
      option.dataset.mode = ["beginner", "explore", "pauper"].includes(mode) ? mode : "standard";
      option.textContent = `${name} · ${{ standard: "Standard", beginner: "Beginner", explore: "Explore", pauper: "Pauper" }[option.dataset.mode]}`;
      select.append(option);
    }
    $("saved-game-picker").hidden = select.options.length < 1;
  }
  function scheduleRender() {
    if (state.renderPending) return;
    state.renderPending = true;
    requestAnimationFrame(() => {
      state.renderPending = false;
      render();
    });
  }
  function tileHeight() {
    return (
      state.tileSize *
      (state.ascii
        ? 1
        : (state.selectedAtlas?.tileHeight || 32) /
          (state.selectedAtlas?.tileWidth || 32))
    );
  }
  function mapPadding() {
    const values = !state.ascii && state.selectedAtlas?.projectedFrames?.version === 1
      ? state.selectedAtlas.projectedFrames.padding : null;
    return (values || [0,0,0,0]).map((n,i)=>n/64*(i%2 ? tileHeight() : state.tileSize));
  }
  function resizeCanvas() {
    const [left,top,right,bottom] = mapPadding();
    const dpr = window.devicePixelRatio || 1,
      w = state.width * state.tileSize + left + right,
      h = state.height * tileHeight() + top + bottom;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    const viewport = $("map-container");
    canvas.style.margin = `${Math.floor(
      viewport.clientHeight / 2
    )}px ${Math.floor(viewport.clientWidth / 2)}px`;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, left*dpr, top*dpr);
    ctx.imageSmoothingEnabled = false;
    scheduleRender();
  }
  function paintTile(context, cell, x, y, size, height = size, ground = false) {
    if (!state.ascii && AtlasTiles.paint(context, state.atlas,
        state.selectedAtlas, cell, x, y, size, height, ground,
        ground ? state.cells : null)) return;
    if (cell.char && cell.char !== " ") {
      context.fillStyle = palette[(Number(cell.color) || 0) & 15] || "#b9c6b2";
      context.font = `${Math.floor(
        size * 0.66
      )}px ui-monospace,Menlo,monospace`;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(cell.char, x + size / 2, y + height / 2 + 1);
    }
  }
  function render() {
    updateLocationDetail();
    const [left,top,right,bottom] = mapPadding();
    const s = state.tileSize,
      sh = tileHeight(),
      w = state.width * s,
      h = state.height * sh;
    ctx.fillStyle = "#0c1416";
    ctx.fillRect(-left, -top, w+left+right, h+top+bottom);
    if (!state.active && !preview) return;
    for (const cell of state.cells.values()) {
      if (cell.tile === 1469 && cell.char === " ") continue;
      const x = cell.x * s,
        y = cell.y * sh;
      ctx.fillStyle =
        cell.char === "." || cell.char === "#" ? "#1e2928" : "#182221";
      ctx.fillRect(x, y, s, sh);
    }
    const focus = state.input?.targeting ? state.cursor : state.hover;
    const layered = !state.ascii && AtlasTiles.paintMap(ctx,state.atlas,state.selectedAtlas,state.cells,s,sh,focus,
      {waterPlane: stat("dungeon-level", "level-desc", "dlevel").trim() === "Water"});
    if(!layered)for(const cell of state.cells.values()) {
      if(cell.tile===1469 && cell.char===" ")continue;
      paintTile(ctx,cell,cell.x*s,cell.y*sh,s,sh,true);
    }
    // Indicators follow every sprite, and refer to logical floor squares.
    for(const cell of state.cells.values()) {
      if(cell.tile===1469 && cell.char===" ")continue;
      const x=cell.x*s,y=cell.y*sh;
      if (state.grid) {
        ctx.strokeStyle = "#70857a12";
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, s - 1, sh - 1);
      }
      if (cell.pet) {
        ctx.fillStyle = "#abc7a1";
        ctx.beginPath();
        ctx.arc(x + s - 5, y + 5, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (state.cells.size) {
      const { x, y } = state.player;
      ctx.strokeStyle = "#d8bc80";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x * s + 1.5, y * sh + 1.5, s - 3, sh - 3);
      const corners = [
        [0, 0],
        [1, 0],
        [0, 1],
        [1, 1],
      ];
      ctx.lineWidth = 3;
      for (const [cx, cy] of corners) {
        const xx = x * s + (cx ? s - 2 : 2),
          yy = y * sh + (cy ? sh - 2 : 2);
        ctx.beginPath();
        ctx.moveTo(xx, yy + (cy ? -5 : 5));
        ctx.lineTo(xx, yy);
        ctx.lineTo(xx + (cx ? -5 : 5), yy);
        ctx.stroke();
      }
    }
    if (state.input?.targeting) {
      const { x, y } = state.cursor;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 3;
      ctx.strokeRect(x * s + 3, y * sh + 3, s - 6, sh - 6);
      ctx.beginPath();
      ctx.moveTo(x * s + s / 2, y * sh);
      ctx.lineTo(x * s + s / 2, y * sh + 7);
      ctx.moveTo(x * s + s / 2, (y + 1) * sh - 7);
      ctx.lineTo(x * s + s / 2, (y + 1) * sh);
      ctx.stroke();
    }
    if (state.hover) {
      ctx.fillStyle = "#cae6cf0c";
      ctx.fillRect(state.hover.x * s, state.hover.y * sh, s, sh);
      ctx.strokeStyle = "#b6d5c299";
      ctx.lineWidth = 1;
      ctx.strokeRect(
        state.hover.x * s + 0.5,
        state.hover.y * sh + 0.5,
        s - 1,
        sh - 1
      );
    }
  }
  function centerPlayer() {
    const [left,top] = mapPadding();
    const map = $("map-container"),
      s = state.tileSize,
      position = state.input?.targeting ? state.cursor : state.player;
    map.scrollLeft =
      canvas.offsetLeft + left + position.x * s + s / 2 - map.clientWidth / 2;
    map.scrollTop =
      canvas.offsetTop +
      top +
      position.y * tileHeight() +
      tileHeight() / 2 -
      map.clientHeight / 2;
  }
  function adjustZoom(delta) {
    state.tileSize = Math.max(20, Math.min(80, state.tileSize + delta));
    $("zoom-label").textContent = Math.round((state.tileSize / 40) * 100) + "%";
    resizeCanvas();
    centerPlayer();
  }
  function addMessage(text) {
    if (!text) return;
    state.messages.push(text);
    if (state.messages.length > 300) state.messages.shift();
    const list = $("messages");
    list.querySelector(".journal-empty")?.remove();
    const row = document.createElement("div");
    row.className = "message";
    if (/welcome|level|experience|saved/i.test(text))
      row.classList.add("important");
    const time = document.createElement("span");
    time.className = "message-time";
    time.textContent = String(
      state.stats.time || state.stats.moves || "·"
    ).trim();
    const content = document.createElement("span");
    content.textContent = text;
    row.append(time, content);
    list.append(row);
    while (list.children.length > 300) list.firstElementChild.remove();
    list.scrollTop = list.scrollHeight;
    $("journal-count").textContent = state.messages.length + " observations";
  }
  function stat(...names) {
    for (const n of names)
      if (state.stats[n] !== undefined) return String(state.stats[n]).trim();
    return "—";
  }
  function updateLocationDetail() {
    if (state.playtest) {
      $("location-detail").textContent = `Test start: ${state.playtest.label}${state.playtest.mode === "inspection" ? " · starting map revealed" : ""}`;
      return;
    }
    const location = stat("dungeon-level", "level-desc", "dlevel");
    let branch = null;
    // Status names take priority over reused regional artwork (for example,
    // Quest goals and Fire also use Gehennom material). Never label a named
    // special level from its material, or guess a branch from canonical tiles.
    if (/^Home\s+\d+$/.test(location)) branch = "The Quest";
    else if (/^Tutorial:/.test(location)) branch = "Tutorial";
    else if (["Earth", "Air", "Fire", "Water"].includes(location))
      branch = "The Plane of " + location;
    else if (location === "Astral") branch = "The Astral Plane";
    else if (location === "Fort Ludios") branch = "Fort Ludios";
    else {
      const materials = new Set([...state.cells.values()].map((cell) => cell.material));
      if (materials.has("mines") || materials.has("mines-built"))
        branch = "The Gnomish Mines";
      else if (materials.has("vlad")) branch = "Vlad’s Tower";
      else if (["gehennom", "asmodeus", "valley", "juiblex", "baalz"].some((m) => materials.has(m)))
        branch = "Gehennom";
    }
    const alignment = stat("alignment");
    $("location-detail").textContent = branch
      ? branch + " · " + (alignment !== "—" ? alignment + " adventurer" : "Explore. Observe. Survive.")
      : (alignment !== "—" ? alignment + " adventurer · " : "") + "Explore. Observe. Survive.";
  }
  function updateStatus() {
    let title = stat("title");
    if (title !== "—") {
      const parts = title.split(/\s+the\s+/i);
      $("character-name").textContent = parts[0];
      $("character-subtitle").textContent = parts[1] || title;
    }
    const hp = stat("hitpoints", "hp"),
      maxhp = stat("hitpoints-max", "hpmax", "maxhp"),
      power = stat("power", "pw", "energy"),
      maxpower = stat("power-max", "pwmax", "energymax");
    $("hp-value").textContent = hp + " / " + maxhp;
    $("power-value").textContent = power + " / " + maxpower;
    $("hp-meter").style.width =
      Math.max(0, Math.min(100, (Number(hp) / Number(maxhp)) * 100 || 0)) + "%";
    $("power-meter").style.width =
      Math.max(
        0,
        Math.min(100, (Number(power) / Number(maxpower)) * 100 || 0)
      ) + "%";
    $("hp-meter").style.background =
      Number(hp) < Number(maxhp) * 0.3 ? "#cb847b" : "#93b7a0";
    const attrs = [
      ["strength", "str"],
      ["dexterity", "dx"],
      ["constitution", "co"],
      ["intelligence", "in"],
      ["wisdom", "wi"],
      ["charisma", "ch"],
    ];
    $("attributes")
      .querySelectorAll("b")
      .forEach((el, i) => (el.textContent = stat(...attrs[i])));
    $("armor-value").textContent = stat("armor-class", "ac");
    const xp = state.experience;
    const maxLevel = xp?.next === null;
    const progress = !xp ? 0 : maxLevel ? 100 :
      Math.max(0, Math.min(100, 100 * (xp.points - xp.start) / (xp.next - xp.start)));
    $("level-value").textContent = xp ? `Level ${xp.level}` : "—";
    $("experience-value").textContent = !xp ? "— / — XP" : maxLevel
      ? `${xp.points.toLocaleString()} XP`
      : `${xp.points.toLocaleString()} / ${xp.next.toLocaleString()} XP`;
    $("experience-goal").textContent = !xp ? "" : maxLevel ? "Maximum level" : `Next: ${xp.level + 1}`;
    $("experience-meter").style.width = `${progress}%`;
    $("experience-progress").setAttribute("aria-valuenow", String(Math.round(progress)));
    $("experience-progress").setAttribute("aria-valuetext", !xp ? "Experience unavailable" : maxLevel
      ? `${xp.points} experience points. Maximum level reached.`
      : `${xp.points} of ${xp.next} experience points needed for level ${xp.level + 1}.`);
    $("gold-value").textContent = stat("gold").replace(/^.*?:\s*/, "");
    $("turn-value").textContent = stat("time", "moves");
    let location = stat("dungeon-level", "level-desc", "dlevel");
    if (location !== "—") {
      $("location-name").textContent = location.replace(
        /^Dlvl:\s*(\d+)$/,
        "Dungeon level $1"
      );
    }
    updateLocationDetail();
    const conditions = $("conditions");
    conditions.replaceChildren();
    for (const val of [stat("hunger"), stat("carrying-capacity", "cap")]) {
      if (val !== "—" && val !== "") {
        const tag = document.createElement("span");
        tag.className = "condition";
        tag.textContent = val;
        conditions.append(tag);
      }
    }
    const bits = Number(stat("condition"));
    const labels = [
      "Bare handed",
      "Blind",
      "Busy",
      "Confused",
      "Deaf",
      "Iron discomfort",
      "Flying",
      "Food poisoned",
      "Glowing hands",
      "Grabbing",
      "Hallucinating",
      "Held",
      "Icy",
      "In lava",
      "Levitating",
      "Paralyzed",
      "Riding",
      "Sleeping",
      "Slimed",
      "Slippery",
      "Petrifying",
      "Strangled",
      "Stunned",
      "Submerged",
      "Terminally ill",
      "Tethered",
      "Trapped",
      "Unconscious",
      "Wounded legs",
      "Holding",
    ];
    labels.forEach((label, i) => {
      if (bits & (1 << i)) {
        const tag = document.createElement("span");
        tag.className = "condition";
        tag.textContent = label;
        conditions.append(tag);
      }
    });
  }
  function inspectCell(x, y) {
    state.hover = { x, y };
    $("coordinate-label").textContent = `${x}, ${y}`;
    scheduleRender();
    const cell = state.cells.get(`${x},${y}`);
    if (!cell) {
      showInspector({
        x,
        y,
        text: "Unexplored territory. Your adventurer has not seen this part of the dungeon.",
      });
      return;
    }
    showInspector({ x, y, text: cell.description || "Observing…" });
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => send({ action: "inspect", x, y }), 75);
  }
  function showInspector(event) {
    if (state.hover && (event.x !== state.hover.x || event.y !== state.hover.y))
      return;
    const cell = state.cells.get(`${event.x},${event.y}`);
    const text = (event.text || "Nothing more is known.")
      .replace(/\\G[0-9a-f]{8}/gi, "")
      .trim();
    const known = !!cell && cell.char !== " ";
    $("inspector-kind").textContent = cell?.pet
      ? "YOUR COMPANION"
      : known
      ? "IN YOUR FIELD OF VIEW"
      : "BEYOND THE KNOWN";
    const clean = text.replace(/^\s*\([^)]*\)\s*/, "");
    const subject = (clean.match(/\(([^)]+)\)/)?.[1] || clean).replace(
      /\s+called\s+.*$/i,
      ""
    );
    const sentence = subject.split(/[.!]\s/)[0];
    $("inspector-title").textContent =
      sentence.length < 60
        ? (sentence.charAt(0).toUpperCase() + sentence.slice(1)).replace(
            /\.$/,
            ""
          )
        : known
        ? "A closer look"
        : "Unexplored";
    $("inspector-description").textContent = text;
    const icon = $("inspector-icon");
    icon.replaceChildren();
    if (cell && state.atlas && !state.ascii) {
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 64;
      const cx = c.getContext("2d");
      cx.imageSmoothingEnabled = false;
      const ratio =
          (state.selectedAtlas?.tileWidth || 32) /
          (state.selectedAtlas?.tileHeight || 32),
        w = Math.min(64, 64 * ratio),
        h = Math.min(64, 64 / ratio);
      paintTile(cx, cell, (64 - w) / 2, (64 - h) / 2, w, h);
      icon.append(c);
    } else icon.textContent = cell?.char?.trim() || "⌖";
    $("inspector-details").replaceChildren();
    if (known) {
      const row = document.createElement("div");
      row.className = "inspect-detail";
      const label = document.createElement("span");
      label.textContent = "Position";
      const value = document.createElement("span");
      value.textContent = `${event.x} · ${event.y}`;
      row.append(label, value);
      $("inspector-details").append(row);
      if (event.beneath?.name === "Throne") {
        const feature = document.createElement("div");
        feature.className = "inspect-detail";
        const label = document.createElement("span");
        label.textContent = "Beneath";
        const value = document.createElement("span");
        value.textContent = event.beneath.remembered ? "Throne (remembered)" : "Throne";
        feature.append(label, value);
        $("inspector-details").append(feature);
      }
    }
  }
  async function chooseAtlas(id) {
    const atlas = state.tilesets.find((t) => t.id === id);
    if (id !== "ascii" && !atlas) return;
    const request = ++state.atlasRequest;
    preference("tileset", id);
    $("tileset-select").value = id;
    // Discard the previous image while the current choice loads. Readable
    // glyphs remain available; an old image must not acquire the new label.
    state.atlas = null;
    state.selectedAtlas = null;
    state.ascii = true;
    if (state.hover)
      showInspector({ ...state.hover, text: $("inspector-description").textContent });
    if (id === "ascii") {
      state.tileSize = 40;
      $("zoom-label").textContent = "100%";
      $("tileset-label").textContent = "Typography / ASCII";
      $("tileset-credit").textContent = "The original language of the dungeon.";
      resizeCanvas();
      centerPlayer();
      return;
    }
    $("tileset-label").textContent = (atlas.name || atlas.id) + " · loading…";
    $("tileset-credit").textContent = "Showing readable glyphs while the tileset loads.";
    resizeCanvas();
    const img = new Image();
    img.onload = () => {
      if (request !== state.atlasRequest) return;
      state.atlas = img;
      state.selectedAtlas = atlas;
      state.ascii = false;
      state.tileSize = Math.max(20, Math.min(80, atlas.preferredTileSize || 40));
      $("zoom-label").textContent = Math.round(state.tileSize / 40 * 100) + "%";
      $("tileset-label").textContent = atlas.name || atlas.id;
      $("tileset-credit").textContent = [atlas.credit, atlas.license]
        .filter(Boolean)
        .join(" · ");
      resizeCanvas();
      centerPlayer();
      if (state.hover)
        showInspector({
          x: state.hover.x,
          y: state.hover.y,
          text: $("inspector-description").textContent,
        });
    };
    img.onerror = () => {
      if (request !== state.atlasRequest) return;
      toast("This tileset could not be loaded. Showing readable glyphs.");
      chooseAtlas("ascii");
    };
    img.src = atlas.path || atlas.url || atlas.file;
  }
  function configureTilesets(tilesets) {
    const custom = native ? null : savedPreferences.customAtlas;
    state.tilesets = [...(tilesets || [])];
    if (custom) {
      state.tilesets = state.tilesets.filter((t) => t.id !== custom.id);
      state.tilesets.push(custom);
    }
    state.tilesets = state.tilesets.map((t) => ({
      ...t,
      path:
        t.path ||
        t.url ||
        (t.file?.startsWith("data:") ? t.file : "../assets/tiles/" + t.file),
    }));
    const select = $("tileset-select");
    select.replaceChildren();
    for (const t of state.tilesets) {
      const option = document.createElement("option");
      option.value = t.id;
      option.textContent = t.name;
      select.append(option);
    }
    const ascii = document.createElement("option");
    ascii.value = "ascii";
    ascii.textContent = "Typography / ASCII";
    select.append(ascii);
    const selected = savedPreferences.tileset;
    if (selected === "ascii" || state.tilesets.some((t) => t.id === selected)) {
      select.value = selected;
      chooseAtlas(selected);
    } else if (state.tilesets.length) {
      select.value = state.tilesets[0].id;
      chooseAtlas(state.tilesets[0].id);
    } else chooseAtlas("ascii");
  }
  function updateMenuHint() {
    $("menu-hint").textContent = state.menuCount
      ? `Quantity: ${state.menuCount} — choose an item. Escape clears the quantity.`
      : "Type a quantity before an item’s letter. Category symbols select groups.";
  }
  function markMenuRow(row, selected, count) {
    row.dataset.selected = String(selected);
    row.dataset.count = String(selected ? count : -1);
    row.classList.toggle("selected", selected);
    row.setAttribute("aria-pressed", String(selected));
    const quantity = row.querySelector(".menu-quantity");
    quantity.hidden = !selected || count < 1;
    quantity.textContent = count > 0 ? "× " + count : "";
  }
  function closeEngineDialog() {
    $("direction-bar").hidden = true;
    $("target-bar").hidden = true;
    $("engine-dialog").close();
    state.input = null;
    restoreMapPointer();
    $("dialog-options").replaceChildren();
    $("dialog-input").value = "";
    state.menuCount = "";
    $("dialog-context").hidden = true;
    $("dialog-messages").replaceChildren();
    scheduleRender();
  }
  function respondInput(data) {
    if (state.input?.kind === "yn" && data.action === "key") {
      const answer = AtlasInput.answerForKey(state.input, data.key);
      if (answer === null) {
        toast("Choose one of the available responses.");
        return false;
      }
      data.key = answer;
    }
    $("toast").classList.remove("visible");
    closeEngineDialog();
    state.waiting = false;
    send(data);
    canvas.focus();
  }
  function showInput(event) {
    state.pendingAction = false;
    $("map-hint").hidden = !!(event.targeting || event.direction);
    $("actions-dialog").close();
    $("direction-bar").hidden = true;
    $("target-bar").hidden = true;
    state.command = event.kind === "key" && event.command !== false;
    if (state.command) state.commandInput = event;
    document
      .querySelectorAll(
        "[data-command],#save-button,#inventory-button,#actions-button,.context-action"
      )
      .forEach((el) => (el.disabled = !state.command));
    if (event.direction) {
      closeEngineDialog();
      state.input = event;
      state.command = false;
      state.waiting = false;
      $("direction-prompt").textContent = event.prompt || "Choose a direction";
      $("direction-bar").hidden = false;
      $("engine-state").textContent = "Choose a direction";
      setStatus(
        "Choose a direction · Arrow keys or compass buttons · Esc returns to NetHack"
      );
      canvas.focus();
      if (state.follow) centerPlayer();
      return;
    }
    if (event.kind === "key" && event.targeting) {
      closeEngineDialog();
      state.input = event;
      state.waiting = false;
      $("target-bar").hidden = false;
      $("engine-state").textContent = "Choose a location";
      setStatus("Click a tile to select · Arrow keys move the cursor · Enter selects · Esc cancels selection");
      canvas.focus();
      scheduleRender();
      if (state.follow) centerPlayer();
      return;
    }
    if (event.kind === "key") {
      if ($("engine-dialog").open) closeEngineDialog();
      state.waiting = true;
      state.input = null;
      if (state.command) state.promptMessages = [];
      $("engine-state").textContent = state.command
        ? "Your turn"
        : "Waiting for a key";
      if (state.command)
        setStatus("Arrow keys to move · Hover over a tile to inspect");
      if (state.command && state.hover && !smoke.enabled) {
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(() => {
          if (state.waiting && state.command && state.hover)
            send({ action: "inspect", ...state.hover });
        }, 75);
      }
      return;
    }
    state.waiting = false;
    state.input = event;
    state.menuCount = "";
    $("menu-hint").hidden = event.kind !== "menu" || event.how === 0;
    updateMenuHint();
    const dialog = $("engine-dialog");
    $("dialog-title").textContent =
      event.prompt ||
      {
        menu: "Your inventory",
        line: "A few words…",
        yn: "Your choice",
        text: "A moment in the dungeon",
      }[event.kind];
    $("dialog-text").textContent = event.lines?.join("\n") || "";
    // Keep the engine's preceding effects readable while the modal covers the
    // journal. These are observations, never inferred item identities.
    const messages = $("dialog-messages");
    messages.replaceChildren();
    for (const text of state.promptMessages) {
      if (text === event.prompt) continue;
      const row = document.createElement("p");
      row.textContent = text;
      messages.append(row);
    }
    $("dialog-context").hidden = !messages.children.length;
    $("dialog-options").replaceChildren();
    $("dialog-input").hidden = event.kind !== "line";
    $("dialog-input").value = event.kind === "line" ? event.default || "" : "";
    $("dialog-input").inputMode =
      event.purpose === "count" ? "numeric" : "text";
    $("dialog-submit").hidden = event.kind === "yn";
    $("dialog-cancel").hidden =
      event.kind === "text" || (event.kind === "menu" && event.how === 0);
    $("dialog-submit").textContent =
      event.kind === "menu" && event.how === 2
        ? "Confirm selection"
        : "Continue";
    if (event.kind === "menu") {
      for (const item of event.items || []) {
        if (!item.selectable) {
          const heading = document.createElement("div");
          heading.className = "menu-heading";
          heading.textContent = item.text;
          $("dialog-options").append(heading);
          continue;
        }
        const row = document.createElement("button");
        row.type = "button";
        row.className = "menu-row" + (item.selected ? " selected" : "");
        row.dataset.id = item.id;
        row.dataset.key = item.key || "";
        row.dataset.group = item.group || "";
        row.dataset.count = "-1";
        row.dataset.selected = item.selected ? "true" : "false";
        const accelerator = document.createElement("span");
        accelerator.className = "accelerator";
        accelerator.textContent = item.key || "·";
        const label = document.createElement("span");
        label.textContent = item.text;
        const quantity = document.createElement("span");
        quantity.className = "menu-quantity";
        quantity.hidden = true;
        row.append(accelerator, label, quantity);
        row.onclick = () => {
          if (event.how === 0) return;
          const count = AtlasInput.menuCount(state.menuCount);
          state.menuCount = "";
          updateMenuHint();
          if (event.how === 1)
            respondInput({
              action: "menu",
              selections: [{ id: item.id, count }],
            });
          else
            markMenuRow(
              row,
              count > 0 || row.dataset.selected !== "true",
              count
            );
        };
        row.setAttribute("aria-pressed", row.dataset.selected);
        $("dialog-options").append(row);
      }
    }
    if (event.kind === "yn") {
      const choices = event.choices || "";
      const group = document.createElement("div");
      group.className = "yn-options";
      const labels = { y: "Yes", n: "No", q: "Cancel" };
      for (const ch of choices) {
        if (ch === "\x1b") break;
        if (/[\s\[\]]/.test(ch)) continue;
        const b = document.createElement("button");
        b.type = "button";
        b.dataset.answer = ch;
        b.dataset.label = event.choiceLabels?.[ch] || labels[ch] || ch;
        b.textContent = b.dataset.label +
          (ch === event.default ? " ↵" : "");
        b.onclick = () => respondInput({ action: "key", key: ch });
        group.append(b);
      }
      if (!choices) {
        const note = document.createElement("p");
        note.textContent = "Type the symbol or letter requested above. Esc cancels.";
        group.append(note);
      }
      $("dialog-options").append(group);
      group.addEventListener("focusin", (focus) => {
        for (const button of group.querySelectorAll("button"))
          button.textContent = button.dataset.label + (button === focus.target ? " ↵" : "");
      });
      group.addEventListener("focusout", (focus) => {
        if (!group.contains(focus.relatedTarget))
          for (const button of group.querySelectorAll("button")) button.textContent = button.dataset.label;
      });
    }
    if (!dialog.open) dialog.showModal();
    messages.scrollTop = messages.scrollHeight;
    if (event.kind === "line") setTimeout(() => $("dialog-input").focus(), 0);
    else if (event.kind === "yn") {
      const buttons = [...$("dialog-options").querySelectorAll("[data-answer]")];
      const title = $("dialog-title");
      title.tabIndex = -1;
      (buttons.find(b => b.dataset.answer === event.default) || title).focus();
    }
    else $("dialog-submit").focus();
  }
  window.receiveNative = function (event) {
    if (typeof event === "string") {
      try {
        event = JSON.parse(event);
      } catch {
        return;
      }
    }
    if (Array.isArray(event)) {
      for (const e of event) window.receiveNative(e);
      return;
    }
    if (!event || !event.type) return;
    switch (event.type) {
      case "boot":
        state.playtest = event.playtest || null;
        if (event.tilesets) configureTilesets(event.tilesets);
        if (event.savedGames) showSavedGames(event.savedGames);
        if (event.version) $("engine-version").textContent = event.version;
        $("load-button").disabled = !event.hasSave;
        $("load-button").title = event.hasSave
          ? "Resume your saved game"
          : "No saved adventure yet";
        if (event.name || event.playerName)
          $("player-name").value = event.name || event.playerName;
        if (event.selfTest && !smoke.enabled) {
          if (["prompt-messages", "pet-target", "lantern-gameplay", "lantern-bars", "court-inspection", "oracle-dialog", "room-shape"].includes(event.testScenario)) {
            smoke.enabled = true;
            smoke.scenario = event.testScenario;
            if (smoke.scenario === "room-shape") {
              smoke.roomBounds = JSON.parse(event.testRoomBounds);
              smoke.terrainTiles = JSON.parse(event.testTerrainTiles || "[]");
            }
            smoke.stage = "prompt-start";
            smoke.promptIndex = smoke.promptAttempts = 0;
            setTimeout(() => {
              if (["oracle-dialog", "room-shape"].includes(smoke.scenario)) $("saved-game-select").value = "wizard";
              if (["lantern-gameplay", "lantern-bars", "court-inspection"].includes(smoke.scenario))
                $("saved-game-select").value = "AtlasContext";
              if ($("load-button").disabled)
                diagnostic("complete", false, "No saved prompt fixture is available");
              else $("load-button").click();
            }, 100);
            break;
          }
          smoke.enabled = true;
          smoke.stage = "start";
          smoke.gender = event.testGender || "female";
          smoke.mode = ["beginner", "explore", "pauper"].includes(event.testMode) ? event.testMode : "standard";
          smoke.nudist = !!event.testNudist;
          smoke.blind = !!event.testBlind;
          smoke.deaf = !!event.testDeaf;
          smoke.noStartingPet = !!event.testNoStartingPet;
          diagnostic(
            "boot",
            true,
            "Native bridge connected; starting smoke adventure"
          );
          setTimeout(() => {
            $("player-name").value = "AtlasSmoke";
            $("player-role").value = "Wizard";
            $("player-race").value = "human";
            updateCharacterChoices();
            $("player-gender").value = smoke.gender;
            $("player-alignment").value = "neutral";
            $("player-mode").value = smoke.mode;
            updateModeHelp();
            $("player-nudist").checked = smoke.nudist;
            $("player-blind").checked = smoke.blind;
            $("player-deaf").checked = smoke.deaf;
            $("player-no-pet").checked = smoke.noStartingPet;
            updateModeHelp();
            if (smoke.blind || smoke.deaf || smoke.noStartingPet)
              smokeCheck("starting-conditions",
                $("player-blind").checked === smoke.blind &&
                $("player-deaf").checked === smoke.deaf &&
                $("player-no-pet").checked === smoke.noStartingPet,
                "Requested starting conditions appear in the creation form");
            if (smoke.nudist) smokeCheck("nudist-creation",
              !$('nudist-option').hidden && !$('player-nudist').disabled &&
              $('player-nudist').checked,
              "Nudist start is selected in the new-game form");
            if (smoke.mode === "beginner") {
              smokeCheck("beginner-creation",
                $("mode-help").textContent.includes("magic whistle") &&
                $("mode-help").textContent.includes("1,000 gold"),
                "Beginner supplies are shown before character creation");
            }
            if (smoke.mode === "explore") smokeCheck("explore-creation",
              $("mode-help").textContent.includes("non-scoring") &&
              $("mode-help").textContent.includes("wand of wishing"),
              "Explore creation explains native non-scoring play and its starting wand");
            if (smoke.mode === "pauper") smokeCheck("pauper-creation",
              $("mode-help").textContent.includes("no items or spells") &&
              $("mode-help").textContent.includes("trained weapon"),
              "Pauper creation explains the starting rules");
            setTimeout(() => $("new-game-form").requestSubmit(),
              smoke.mode !== "standard" ? 900 : 0);
          }, 100);
        }
        break;
      case "hello":
        state.width = event.width || 80;
        state.height = event.height || 21;
        $("engine-version").textContent = event.version || "5.0";
        resizeCanvas();
        break;
      case "started":
        state.startPending = false;
        state.promptMessages = [];
        state.experience = null;
        setAdventureMode(event.mode);
        $("welcome").hidden = true;
        $("map-empty").hidden = true;
        setActive(true);
        setStatus("Arrow keys to move · Hover over a tile to inspect");
        canvas.focus();
        break;
      case "cell":
        state.cells.set(`${event.x},${event.y}`, event);
        scheduleRender();
        break;
      case "clear":
        if (event.window === "map" || !event.window) {
          state.cells.clear();
          scheduleRender();
        }
        break;
      case "cursor":
        state.cursor = { x: event.x, y: event.y };
        state.player = { x: event.playerX ?? event.x, y: event.playerY ?? event.y };
        scheduleRender();
        if (state.follow) centerPlayer();
        break;
      case "status":
        state.stats[event.name] = event.value;
        break;
      case "statusFlush":
        state.experience = event.experience || null;
        updateStatus();
        scheduleRender();
        break;
      case "message":
        if (event.text) {
          state.promptMessages.push(event.text);
          if (state.promptMessages.length > 300) state.promptMessages.shift();
        }
        addMessage(event.text);
        break;
      case "input":
        if (!state.active) {
          setActive(true);
          $("welcome").hidden = true;
          $("map-empty").hidden = true;
        }
        showInput(event);
        break;
      case "commands":
        state.commands = event.commands || [];
        renderContextActions();
        if ($("actions-dialog").open) renderActions();
        break;
      case "context":
        state.contextActions = event.commands || [];
        renderContextActions();
        break;
      case "commandRejected":
        if (state.pendingAction && state.commandInput)
          showInput(state.commandInput);
        toast(event.text || "That action is unavailable at this prompt.");
        break;
      case "inspect":
        showInspector(event);
        break;
      case "exit": {
        if (event.reason === "playtest-report") {
          closeEngineDialog();
          state.waiting = false;
          $("engine-state").textContent = "Saving report…";
          setStatus("Saving a report snapshot; your game will resume.");
          break;
        }
        const exitText =
          event.code && event.detail
            ? `NetHack stopped unexpectedly: ${event.detail}`
            : event.text ||
              (event.code
                ? "NetHack stopped unexpectedly."
                : "Your adventure has ended.");
        if (event.code) toast(exitText);
        closeEngineDialog();
        $("actions-dialog").close();
        state.waiting = false;
        setActive(false);
        state.mode = null;
        $("adventure-mode").hidden = true;
        $("beginner-help").hidden = true;
        $("explore-help").hidden = true;
        $("pauper-help").hidden = true;
        addMessage(exitText);
        setStatus(exitText);
        $("welcome").hidden = false;
        $("welcome-footnote").textContent = exitText;
        if (event.hasSave !== undefined)
          $("load-button").disabled = !event.hasSave;
        if (event.savedGames) showSavedGames(event.savedGames);
        state.startPending = false;
        document.querySelector("#new-game-form button").disabled = false;
        break;
      }
      case "error":
        toast(event.text || event.message || "An unexpected error occurred.");
        setStatus(event.text || event.message || "Unable to start adventure.");
        state.startPending = false;
        document.querySelector("#new-game-form button").disabled = false;
        break;
      case "tilesetImported":
      case "tileset":
        if (event.tileset) {
          let persisted = event.persistent === true;
          if (!native) persisted = preference("customAtlas", event.tileset);
          preference("tileset", event.tileset.id);
          state.tilesets = state.tilesets.filter(
            (t) => t.id !== event.tileset.id
          );
          state.tilesets.push(event.tileset);
          configureTilesets(state.tilesets);
          $("tileset-select").value = event.tileset.id;
          chooseAtlas(event.tileset.id);
          toast(
            persisted
              ? "Custom tileset imported and saved."
              : "Custom tileset loaded for this session; it could not be saved."
          );
        }
        break;
      case "saved":
        toast(event.text || "Adventure saved.");
        break;
    }
    smokeEvent(event);
  };
  function characterSelection() {
    return Object.fromEntries(
      ["role", "race", "gender", "alignment"].map((field) => [
        field,
        $("player-" + field).value,
      ])
    );
  }
  function updateCharacterChoices() {
    const selection = AtlasCharacter.resolve(characterSelection());
    const choices = AtlasCharacter.choices(selection);
    for (const [field, allowed] of [
      ["race", choices.races],
      ["gender", choices.genders],
      ["alignment", choices.alignments],
    ]) {
      const select = $("player-" + field);
      for (const option of select.options) {
        option.disabled =
          !option.value ||
          (option.value !== "random" && !allowed.includes(option.value));
      }
      select.value = selection[field];
    }
    const restrictions = [];
    if (choices.races.length === 1)
      restrictions.push("Race: " + choices.races[0]);
    if (choices.genders.length === 1)
      restrictions.push("Sex: " + choices.genders[0]);
    if (choices.alignments.length === 1)
      restrictions.push("Alignment: " + choices.alignments[0]);
    $("alignment-help").textContent = restrictions.length
      ? "Required by your choices: " + restrictions.join(" · ") + "."
      : "Available choices follow NetHack’s role and race restrictions.";
  }
  function updateModeHelp() {
    const mode = $("player-mode").value;
    $("nudist-option").hidden = mode === "pauper";
    $("player-nudist").disabled = $("nudist-option").hidden;
    $("starting-help").textContent = mode === "beginner" && $("player-blind").checked
      ? "Blindness hides the nearby Beginner chest until you find it. You can tame a pet later."
      : mode === "pauper"
      ? "Pauper includes Nudist. Blind and Deaf persist. You can tame a pet later."
      : "Nudist omits starting armor. Blind and Deaf persist. You can tame a pet later.";
    $("mode-help").textContent = mode === "explore"
      ? "NetHack’s non-scoring discovery mode. Start with a wand of wishing and choose whether to accept death. Separate saves; no Beginner supply chest."
      : mode === "pauper"
      ? "Start with no items or spells, and no trained weapon or spell skills. Normal death and scoring rules; separate saves."
      : mode === "beginner"
      ? "A named supply chest nearby holds 1,000 gold, an identified uncursed magic whistle, 2 food rations and an identified uncursed healing potion. Move onto its square and choose Loot. Your role keeps its usual gear. Normal combat and death rules apply."
      : "Your role’s usual supplies. Normal NetHack rules apply.";
  }
  ["role", "race", "gender", "alignment"].forEach((field) => {
    $("player-" + field).addEventListener("change", updateCharacterChoices);
  });
  updateCharacterChoices();
  $("player-mode").addEventListener("change", updateModeHelp);
  $("player-blind").addEventListener("change", updateModeHelp);
  updateModeHelp();
  $("new-game-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.startPending) return;
    if (!AtlasCharacter.valid(characterSelection())) {
      toast("Choose a valid role, race, sex and alignment.");
      return;
    }
    state.startPending = true;
    document.querySelector("#new-game-form button").disabled = true;
    state.cells.clear();
    state.stats = {};
    $("messages").replaceChildren();
    state.messages = [];
    send({
      action: "start",
      name: $("player-name").value.trim() || "Adventurer",
      role: $("player-role").value,
      race: $("player-race").value,
      gender: $("player-gender").value,
      alignment: $("player-alignment").value,
      mode: $("player-mode").value,
      nudist: !$('player-nudist').disabled && $('player-nudist').checked,
      blind: $("player-blind").checked,
      deaf: $("player-deaf").checked,
      noStartingPet: $("player-no-pet").checked,
    });
  });
  $("load-button").onclick = () => {
    const selected = $("saved-game-select").selectedOptions[0];
    send({ action: "load", name: selected?.value || undefined,
      mode: selected?.dataset.mode || "standard" });
  };
  function requestSave() {
    if (state.active) {
      state.waiting = false;
      send({ action: "save" });
    }
  }
  $("save-button").onclick = requestSave;
  $("inventory-button").onclick = () => key("i", true);
  document
    .querySelectorAll("[data-command]")
    .forEach((b) => (b.onclick = () => key(b.dataset.command, true)));
  function renderContextActions() {
    const panel = $("context-actions");
    const expanded = panel.querySelector("details")?.open || false;
    panel.replaceChildren();
    const displayed = new Set();
    let overflow;
    for (const suggestion of state.contextActions) {
      const command = state.commands.find(
        (item) => item.name === suggestion.name && item.selectable !== false
      );
      if (!command || displayed.has(command.name)) continue;
      displayed.add(command.name);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "context-action";
      button.dataset.action = command.name;
      button.disabled = !state.active || !state.command || !state.waiting;
      const copy = document.createElement("span");
      const title = document.createElement("strong");
      title.textContent = suggestion.label || command.name;
      const reason = document.createElement("small");
      reason.textContent = suggestion.reason;
      copy.append(title, reason);
      const shortcut = document.createElement("kbd");
      shortcut.textContent = (command.keys || [])[0] || "#" + command.name;
      button.append(copy, shortcut);
      button.onclick = () => chooseAction(command);
      if (displayed.size <= 5) panel.append(button);
      else {
        if (!overflow) {
          overflow = document.createElement("details");
          overflow.className = "context-more";
          overflow.open = expanded;
          overflow.append(document.createElement("summary"));
          panel.append(overflow);
        }
        overflow.append(button);
        overflow.firstElementChild.textContent =
          "More actions here (" + (displayed.size - 5) + ")";
      }
    }
    document.querySelectorAll(".quick-actions [data-action-name]").forEach(
      (button) => (button.hidden = displayed.has(button.dataset.actionName))
    );
    panel.hidden = !panel.childElementCount;
  }
  function renderActions() {
    const matches = AtlasInput.filterCommands(
      state.commands,
      $("action-filter").value
    );
    $("action-count").textContent =
      matches.length + " of " + state.commands.length + " actions";
    const list = $("action-results");
    list.replaceChildren();
    if (!matches.length) {
      const empty = document.createElement("p");
      empty.className = "action-empty";
      empty.textContent = state.commands.length
        ? "No matching actions. Try a different word or shortcut."
        : "Start an adventure to load NetHack’s command list.";
      list.append(empty);
    }
    for (const command of matches) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "action-row";
      row.dataset.action = command.name;
      row.disabled =
        command.selectable === false ||
        !state.active ||
        !state.command ||
        !state.waiting;
      const copy = document.createElement("span");
      copy.className = "action-copy";
      const title = document.createElement("strong");
      title.textContent = command.name;
      const description = document.createElement("small");
      description.textContent =
        command.description +
        (command.prefix ? " · Follow with another key" : "") +
        (command.selectable === false ? " · Use its shortcut" : "");
      copy.append(title, description);
      const shortcut = document.createElement("span");
      shortcut.className = "action-shortcuts";
      shortcut.textContent = command.keys.length
        ? command.keys.join(" / ")
        : command.selectable === false
        ? "Key binding only"
        : "#" + command.name;
      row.append(copy, shortcut);
      row.onclick = () => chooseAction(command);
      list.append(row);
    }
  }
  function openActions() {
    if (!state.active || !state.command || !state.waiting || state.input)
      return;
    if (document.querySelector("dialog[open]")) return;
    $("action-filter").value = "";
    renderActions();
    $("actions-dialog").showModal();
    $("action-filter").focus();
  }
  function chooseAction(command) {
    if (
      !state.active ||
      !state.command ||
      !state.waiting ||
      state.input ||
      command.selectable === false
    )
      return;
    $("actions-dialog").close();
    state.pendingAction = true;
    state.waiting = false;
    send({ action: "command", name: command.name });
    canvas.focus();
  }
  $("actions-button").onclick = openActions;
  $("action-filter").addEventListener("input", renderActions);
  $("actions-dialog").addEventListener("keydown", (event) => {
    const rows = [
      ...$("action-results").querySelectorAll("button:not(:disabled)"),
    ];
    const index = rows.indexOf(document.activeElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = event.key === "ArrowDown" ? index + 1 : index - 1;
      if (next < 0) $("action-filter").focus();
      else rows[Math.min(next, rows.length - 1)]?.focus();
    } else if (
      event.key === "Enter" &&
      document.activeElement === $("action-filter")
    ) {
      event.preventDefault();
      rows[0]?.click();
    }
  });
  $("actions-dialog").addEventListener("close", () => canvas.focus());
  $("help-button").onclick = () => $("help-dialog").showModal();
  $("settings-button").onclick = () => $("settings-dialog").showModal();
  document.querySelectorAll("[data-close]").forEach(
    (b) =>
      (b.onclick = () => {
        $(b.dataset.close).close();
        canvas.focus();
      })
  );
  $("zoom-in").onclick = () => adjustZoom(4);
  $("zoom-out").onclick = () => adjustZoom(-4);
  $("center-button").onclick = centerPlayer;
  $("follow-player").onchange = (e) => {
    state.follow = e.target.checked;
    if (state.follow) centerPlayer();
  };
  $("show-grid").onchange = (e) => {
    state.grid = e.target.checked;
    scheduleRender();
  };
  $("tileset-select").onchange = (e) => {
    chooseAtlas(e.target.value);
  };
  $("import-tiles-button").onclick = () => {
    if (native)
      send({
        action: "importTileset",
        tileWidth: Number($("import-tile-width").value),
        tileHeight: Number($("import-tile-height").value),
      });
    else $("import-settings").hidden = !$("import-settings").hidden;
  };
  $("apply-tiles").onclick = () => {
    const file = $("tile-file").files[0],
      size = Number($("tile-width").value);
    if (!file || !size) {
      toast("Choose an atlas image and enter its tile size.");
      return;
    }
    const url = URL.createObjectURL(file),
      img = new Image();
    img.onload = () => {
      const count =
        Math.floor(img.width / size) * Math.floor(img.height / size);
      if (img.width % size || img.height % size || count < 2304) {
        URL.revokeObjectURL(url);
        toast(
          "This image must contain at least 2,304 complete tiles in NetHack 5.0 order."
        );
        return;
      }
      const t = {
        id: "custom-" + Date.now(),
        name: file.name,
        tileWidth: size,
        tileHeight: size,
        columns: img.width / size,
        path: url,
      };
      state.tilesets.push(t);
      configureTilesets(state.tilesets);
      $("tileset-select").value = t.id;
      chooseAtlas(t.id);
      toast("Custom tileset loaded.");
    };
    img.onerror = () => toast("This image could not be opened.");
    img.src = url;
  };
  $("clear-log").onclick = () => {
    $("messages").replaceChildren();
    state.messages = [];
    $("journal-count").textContent = "Journal cleared";
  };
  function restoreMapPointer() {
    if (!mapPointerPosition) return;
    const mapRect = $("map-container").getBoundingClientRect();
    const {clientX,clientY} = mapPointerPosition;
    state.mapPointerInside = clientX >= mapRect.left && clientX < mapRect.right &&
      clientY >= mapRect.top && clientY < mapRect.bottom;
    state.hover = null;
    if (!state.mapPointerInside) return;
    const rect = canvas.getBoundingClientRect(), [left,top] = mapPadding();
    const x = Math.floor((clientX-rect.left-left)/state.tileSize);
    const y = Math.floor((clientY-rect.top-top)/tileHeight());
    if (x >= 0 && x < state.width && y >= 0 && y < state.height)
      state.hover = {x,y};
  }
  // Keep physical coordinates while a modal temporarily owns pointer events.
  // Closing a prompt must not require a mouse movement to restore map focus.
  document.addEventListener("mousemove", event => {
    mapPointerPosition = {clientX:event.clientX,clientY:event.clientY};
  }, true);
  $("map-container").addEventListener("mousemove", (event) => {
    state.mapPointerInside = true;
    const [left,top] = mapPadding();
    const rect = canvas.getBoundingClientRect(),
      x = Math.floor((event.clientX - rect.left - left) / state.tileSize),
      y = Math.floor((event.clientY - rect.top - top) / tileHeight());
    if (x < 0 || x >= state.width || y < 0 || y >= state.height) {
      clearTimeout(hoverTimer); state.hover = null; scheduleRender(); return;
    }
    if (state.hover?.x === x && state.hover?.y === y) return;
    inspectCell(x, y);
  });
  $("map-container").addEventListener("mouseleave", () => {
    state.mapPointerInside = false;
    clearTimeout(hoverTimer);
    state.hover = null;
    scheduleRender();
  });
  canvas.addEventListener("click", (event) => {
    canvas.focus();
    if (event.detail > 1 || document.querySelector("dialog[open]")) return;
    const rect = canvas.getBoundingClientRect();
    const [left,top] = mapPadding();
    const target = {
      x: Math.floor((event.clientX - rect.left - left) / state.tileSize),
      y: Math.floor((event.clientY - rect.top - top) / tileHeight()),
    };
    if (
      target.x < 1 ||
      target.x >= state.width ||
      target.y < 0 ||
      target.y >= state.height
    )
      return;
    const direction = AtlasInput.adjacentDirection(state.player, target);
    if (state.input?.targeting) {
      respondInput({ action: "position", ...target });
    } else if (state.input?.direction) {
      if (direction) answerDirection(direction);
      else if (target.x === state.player.x && target.y === state.player.y)
        answerDirection(".");
      else toast("Click a neighboring tile to choose a direction.");
    } else if (state.command && state.waiting && !state.input) {
      if (direction)
        key(AtlasInput.directionKey(state.commandInput || {}, direction), true);
      else if (target.x !== state.player.x || target.y !== state.player.y)
        toast(
          "Click a neighboring tile to move one step. Hover any tile to inspect it."
        );
    }
  });
  $("dialog-form").onsubmit = (event) => {
    event.preventDefault();
    const input = state.input;
    if (!input) return;
    if (input.kind === "line")
      respondInput({ action: "input", text: $("dialog-input").value });
    else if (input.kind === "menu") {
      const selections = [
        ...$("dialog-options").querySelectorAll('[data-selected="true"]'),
      ].map((row) => ({
        id: Number(row.dataset.id),
        count: Number(row.dataset.count) || -1,
      }));
      respondInput({ action: "menu", selections });
    } else if (input.kind === "text") respondInput({ action: "key", key: " " });
    else if (input.kind === "yn" && input.default)
      respondInput({ action: "key", key: input.default });
  };
  function cancelInput() {
    if (!state.input) return;
    if (state.input.kind === "menu")
      respondInput({ action: "menu", cancel: true, selections: [] });
    else if (state.input.kind === "line")
      respondInput({ action: "input", text: "\x1b" });
    else respondInput({ action: "key", key: "\x1b" });
  }
  function answerDirection(key) {
    if (!state.input?.direction) return;
    respondInput({
      action: "key",
      key: AtlasInput.directionKey(state.input, key),
    });
  }
  document.querySelectorAll("[data-direction]").forEach((button) => {
    button.onclick = () => answerDirection(button.dataset.direction);
  });
  $("direction-cancel").onclick = cancelInput;
  $("target-select").onclick = () => {
    if (state.input?.targeting)
      respondInput({ action: "position", ...state.cursor });
  };
  $("target-cancel").onclick = cancelInput;
  $("dialog-cancel").onclick = cancelInput;
  $("engine-dialog").addEventListener("cancel", (event) => {
    event.preventDefault();
    cancelInput();
  });
  document.addEventListener("keydown", (event) => {
    if (event.metaKey && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if ($("actions-dialog").open) $("actions-dialog").close();
      else openActions();
      return;
    }
    const activeDialog = document.querySelector("dialog[open]");
    if (activeDialog && activeDialog.id !== "engine-dialog") return;
    if (!state.active) return;
    if (event.metaKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      requestSave();
      return;
    }
    if (event.metaKey) return;
    if (event.altKey && state.waiting && !state.input) {
      const ch = event.code?.match(/^Key([A-Z])$/)?.[1]?.toLowerCase();
      if (ch) {
        event.preventDefault();
        key(ch.charCodeAt(0) | 128);
      }
      return;
    }
    if (state.input) {
      const input = state.input;
      if (input.targeting) {
        const arrows = {
          ArrowLeft: "h", ArrowRight: "l", ArrowUp: "k", ArrowDown: "j",
          Home: "y", PageUp: "u", End: "b", PageDown: "n",
        };
        if (event.key === "Enter") {
          event.preventDefault();
          respondInput({ action: "position", ...state.cursor });
        } else if (arrows[event.key] || event.key === "Escape" || event.key.length === 1) {
          event.preventDefault();
          respondInput({ action: "key", key: arrows[event.key]
            ? AtlasInput.directionKey(input, arrows[event.key])
            : event.key === "Escape" ? "\x1b" : event.key });
        }
        return;
      }
      if (input.direction) {
        const arrows = {
          ArrowLeft: "h",
          ArrowRight: "l",
          ArrowUp: "k",
          ArrowDown: "j",
          Home: "y",
          PageUp: "u",
          End: "b",
          PageDown: "n",
        };
        if (event.key === "Escape") {
          event.preventDefault();
          cancelInput();
        } else if (arrows[event.key]) {
          event.preventDefault();
          answerDirection(arrows[event.key]);
        } else if (event.key.length === 1) {
          event.preventDefault();
          respondInput({ action: "key", key: event.key });
        }
        return;
      }
      if (input.kind === "line") return;
      if (event.key === "Escape") {
        event.preventDefault();
        if (input.kind === "menu" && state.menuCount) {
          state.menuCount = "";
          updateMenuHint();
        } else cancelInput();
        return;
      }
      if (input.kind === "yn") {
        if (event.key === "Tab") return;
        if (event.key === "Enter" || event.key.length === 1) {
          event.preventDefault();
          const focused = document.activeElement;
          if ((event.key === "Enter" || event.key === " ") &&
              focused?.tagName === "BUTTON" && $("engine-dialog").contains(focused))
            focused.click();
          else respondInput({ action: "key", key: event.key });
        }
        return;
      }
      if (input.kind === "text") {
        if (["Shift", "Control", "Meta", "Alt"].includes(event.key)) return;
        event.preventDefault();
        respondInput({
          action: "key",
          key:
            event.key === "Enter"
              ? "\n"
              : event.key.length === 1
              ? event.key
              : " ",
        });
        return;
      }
      if (input.kind === "menu") {
        if (event.key === "Enter") {
          event.preventDefault();
          $("dialog-form").requestSubmit();
          return;
        }
        if (event.key === "Backspace" && state.menuCount) {
          event.preventDefault();
          state.menuCount = state.menuCount.slice(0, -1);
          updateMenuHint();
          return;
        }
        if (event.key.length === 1) {
          const rows = [...$("dialog-options").querySelectorAll(".menu-row")];
          const row = rows.find((r) => r.dataset.key === event.key);
          if (input.how > 0 && /^[0-9]$/.test(event.key) && !row) {
            event.preventDefault();
            state.menuCount = (state.menuCount + event.key).slice(0, 8);
            updateMenuHint();
            return;
          }
          if (row) {
            event.preventDefault();
            row.click();
          } else if (input.how === 0 && event.key === " ") {
            event.preventDefault();
            respondInput({ action: "menu", selections: [] });
          } else if (input.how === 2) {
            const group = rows.filter(
              (r) => r.dataset.group && r.dataset.group === event.key
            );
            if (group.length) {
              event.preventDefault();
              const selected = !group.every(
                  (r) => r.dataset.selected === "true"
                ),
                count = AtlasInput.menuCount(state.menuCount);
              group.forEach((r) => markMenuRow(r, selected, count));
              state.menuCount = "";
              updateMenuHint();
            } else if ([".", "-", "@"].includes(event.key)) {
              event.preventDefault();
              rows.forEach((r) =>
                markMenuRow(
                  r,
                  event.key === "." ||
                    (event.key === "@" && r.dataset.selected !== "true"),
                  -1
                )
              );
              state.menuCount = "";
              updateMenuHint();
            }
          }
        }
        return;
      }
    }
    if (
      ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)
    )
      return;
    const arrows = {
      ArrowLeft: "h",
      ArrowRight: "l",
      ArrowUp: "k",
      ArrowDown: "j",
      Home: "y",
      PageUp: "u",
      End: "b",
      PageDown: "n",
    };
    let char = arrows[event.key];
    if (char) char = state.command
      ? AtlasInput.movementKey(state.commandInput || {}, char, event.shiftKey)
      : event.shiftKey ? char.toUpperCase() : char;
    if (!char && event.key === "Escape") char = "\x1b";
    if (!char && event.key === "Enter") char = "\n";
    if (!char && event.key === "Backspace") char = "\b";
    if (!char && event.key.length === 1) char = event.key;
    if (event.ctrlKey && event.key.length === 1)
      char = String.fromCharCode(event.key.toUpperCase().charCodeAt(0) & 31);
    if (char) {
      event.preventDefault();
      key(char);
    }
  });
  window.addEventListener("resize", () => {
    resizeCanvas();
    if (state.follow) centerPlayer();
  });
  resizeCanvas();
  if (preview) {
    const banner = document.createElement("div");
    banner.className = "preview-banner";
    banner.textContent = replay
      ? "ENGINE REPLAY · RECORDED NETHACK 5.0 SESSION"
      : "DESIGN PREVIEW · ILLUSTRATIVE FIXTURE, NOT LIVE GAMEPLAY";
    document.body.append(banner);
    if (replay) loadReplay();
    else loadPreview();
  } else if (native) {
    send({ action: "ready" });
  } else {
    $("welcome-footnote").textContent =
      "Open the bundled macOS application to play.";
    $("load-button").disabled = true;
  }
  async function loadReplay() {
    try {
      const manifest = await fetch("../assets/tiles/manifest.json").then((r) =>
        r.json()
      );
      configureTilesets(manifest.tilesets);
      const events = await fetch("../.artifacts/game-events.json").then((r) =>
        r.json()
      );
      window.receiveNative({ type: "started" });
      let inspection;
      for (const event of events) {
        if (event.type === "input" || event.type === "exit") continue;
        if (event.type === "inspect") {
          if (event.x > 1) inspection = event;
          continue;
        }
        window.receiveNative(event);
      }
      window.receiveNative({ type: "input", kind: "key", command: true });
      if (inspection) {
        state.hover = { x: inspection.x, y: inspection.y };
        showInspector(inspection);
      }
      setTimeout(centerPlayer, 100);
      setStatus("Recorded engine state · open the macOS app for live play");
    } catch (error) {
      toast("Could not open engine transcript: " + error.message);
    }
  }
  async function loadPreview() {
    try {
      const manifest = await fetch("../assets/tiles/manifest.json").then((r) =>
        r.json()
      );
      configureTilesets(
        (manifest.tilesets || manifest).map((t) => ({
          ...t,
          path: t.path || "../assets/tiles/" + (t.file || t.filename),
        }))
      );
    } catch {}
    window.receiveNative({ type: "started" });
    window.receiveNative({ type: "input", kind: "key" });
    state.stats = {
      title: "Ariadne the Skirmisher",
      strength: "18/01",
      dexterity: 14,
      constitution: 18,
      intelligence: 9,
      wisdom: 11,
      charisma: 10,
      hitpoints: 24,
      "hitpoints-max": 28,
      power: 6,
      "power-max": 8,
      "armor-class": 3,
      "experience-level": 3,
      gold: 142,
      time: 287,
      "dungeon-level": "Dlvl: 3",
      alignment: "Neutral",
    };
    state.experience = { level: 3, points: 65, start: 40, next: 80 };
    updateStatus();
    const rooms = [
      [30, 4, 41, 11],
      [47, 6, 59, 14],
      [20, 12, 32, 18],
    ];
    for (const [x1, y1, x2, y2] of rooms)
      for (let y = y1; y <= y2; y++)
        for (let x = x1; x <= x2; x++) {
          const wall = x === x1 || x === x2 || y === y1 || y === y2;
          const ch = wall ? (y === y1 || y === y2 ? "─" : "│") : ".";
          state.cells.set(`${x},${y}`, {
            x,
            y,
            char: ch,
            color: wall ? 8 : 7,
            tile: wall
              ? x === x1
                ? y === y1
                  ? 1275
                  : y === y2
                  ? 1277
                  : 1273
                : x === x2
                ? y === y1
                  ? 1276
                  : y === y2
                  ? 1278
                  : 1273
                : 1274
              : 1291,
            description: wall ? "A stone wall." : "The floor of a room.",
          });
        }
    for (let x = 41; x <= 47; x++)
      state.cells.set(`${x},8`, {
        x,
        y: 8,
        char: "#",
        color: 7,
        tile: 1294,
        description: "A dimly lit corridor.",
      });
    for (let y = 11; y <= 15; y++)
      state.cells.set(`34,${y}`, {
        x: 34,
        y,
        char: "#",
        color: 7,
        tile: 1294,
        description: "A dimly lit corridor.",
      });
    for (let x = 32; x <= 34; x++)
      state.cells.set(`${x},15`, {
        x,
        y: 15,
        char: "#",
        color: 7,
        tile: 1294,
        description: "A dimly lit corridor.",
      });
    const fixtures = [
      {
        x: 36,
        y: 8,
        char: "@",
        color: 15,
        tile: 699,
        description: "Ariadne, a neutral human Valkyrie.",
      },
      {
        x: 37,
        y: 8,
        char: "d",
        color: 7,
        tile: 32,
        pet: true,
        description: "A tame little dog. Your faithful companion.",
      },
      {
        x: 39,
        y: 6,
        char: "g",
        color: 2,
        tile: 144,
        description: "A goblin. It carries an orcish dagger.",
      },
      {
        x: 34,
        y: 6,
        char: "!",
        color: 1,
        tile: 1088,
        description: "A ruby potion. Its contents are unknown.",
      },
      {
        x: 52,
        y: 10,
        char: "$",
        color: 11,
        tile: 1229,
        description: "A pile of gold pieces.",
      },
      {
        x: 55,
        y: 12,
        char: ">",
        color: 7,
        tile: 1298,
        description: "A staircase down.",
      },
      {
        x: 25,
        y: 15,
        char: ")",
        color: 7,
        tile: 825,
        description: "A crude dagger lies here.",
      },
    ];
    fixtures.forEach((c) => state.cells.set(`${c.x},${c.y}`, c));
    state.player = { x: 36, y: 8 };
    state.tileSize = 40;
    resizeCanvas();
    setTimeout(centerPlayer, 60);
    [
      "Hello Ariadne, welcome to NetHack! You are a neutral human Valkyrie.",
      "You descend the stairs.",
      "Your little dog follows you.",
      "You see here a ruby potion.",
      "You hear the footsteps of a guard on patrol.",
    ].forEach(addMessage);
    state.hover = { x: 39, y: 6 };
    showInspector({
      x: 39,
      y: 6,
      text: "A goblin. It carries an orcish dagger.",
    });
  }
  function previewAction(data) {
    if (data.action === "inspect") {
      const c = state.cells.get(`${data.x},${data.y}`);
      showInspector({
        x: data.x,
        y: data.y,
        text: c?.description || "Unexplored territory.",
      });
    } else if (data.action === "key") {
      if (data.key === "i")
        showInput({
          type: "input",
          kind: "menu",
          how: 0,
          prompt: "Your inventory",
          items: [
            { id: 0, text: "Weapons", selectable: false },
            {
              id: 1,
              text: "a +1 long sword (weapon in hand)",
              key: "a",
              selectable: true,
            },
            { id: 2, text: "a +0 dagger", key: "b", selectable: true },
            { id: 3, text: "Armor", selectable: false },
            {
              id: 4,
              text: "an uncursed +3 small shield (being worn)",
              key: "c",
              selectable: true,
            },
            { id: 5, text: "Comestibles", selectable: false },
            {
              id: 6,
              text: "2 uncursed food rations",
              key: "d",
              selectable: true,
            },
          ],
        });
      else {
        toast(
          "Design preview — launch the macOS app for real NetHack gameplay."
        );
        state.waiting = true;
      }
    } else if (data.action === "save") {
      toast("Design preview — launch the macOS app to save a real adventure.");
      state.waiting = true;
    } else if (data.action === "menu" || data.action === "input") {
      state.waiting = true;
    } else if (data.action === "start" || data.action === "load") {
      loadPreview();
    }
  }
})();
