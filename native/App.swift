import Cocoa
import UniformTypeIdentifiers
import WebKit

// A native, offline application. WebKit supplies rendering, never game logic.
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKScriptMessageHandler,
  WKNavigationDelegate
{
  var window: NSWindow!
  var web: WKWebView!
  var engine: Process?
  var input: FileHandle?
  var readPipe: Pipe?
  var errorPipe: Pipe?
  var pending = Data()
  var events = [[String: Any]]()
  var flushScheduled = false
  var ioTimer: Timer?
  var ready = false
  var closing = false
  var stderrTail = ""
  var playerName = "Adventurer"
  var playMode = "standard"
  var currentInput = ""
  var playtestTimer: Timer?
  var playtestLock: Int32 = -1
  var playtestAutoStarted = false
  var playtestLiveDestination: String?
  var liveSetupStage = 0
  var playtestRestoring = false
  var reportDestination: URL?
  var reportShouldResume = false
  let selfTest = ProcessInfo.processInfo.arguments.contains("--self-test")
  var preferences: UserDefaults {
    (selfTest || playtestRun != nil) ? UserDefaults(suiteName: "run.nethack.atlas.selftest")! : .standard
  }
  var diagnosticsURL: URL? {
    ProcessInfo.processInfo.environment["ATLAS_DIAGNOSTICS"].map { URL(fileURLWithPath: $0) }
  }
  let fm = FileManager.default
  let resources = Bundle.main.resourceURL!
  var dataDirectory: URL!
  var tileManifest = [[String: Any]]()

  func applicationDidFinishLaunching(_ notification: Notification) {
    NSApp.setActivationPolicy(.regular)
    NSApp.appearance = NSAppearance(named: .darkAqua)
    configureMenu()
    let configuration = WKWebViewConfiguration()
    configuration.userContentController.add(self, name: "nethack")
    configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
    if selfTest || playtestRun != nil { configuration.websiteDataStore = .nonPersistent() }
    web = WKWebView(frame: .zero, configuration: configuration)
    web.navigationDelegate = self
    web.setValue(false, forKey: "drawsBackground")
    window = NSWindow(
      contentRect: NSRect(x: 0, y: 0, width: 1440, height: 930),
      styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
      backing: .buffered, defer: false)
    window.title = "Atlas for NetHack"
    window.titlebarAppearsTransparent = true
    window.titleVisibility = .hidden
    window.backgroundColor = NSColor(calibratedRed: 0.035, green: 0.048, blue: 0.065, alpha: 1)
    window.minSize = NSSize(width: 1000, height: 700)
    window.contentView = web
    window.delegate = self
    window.center()
    window.setFrameAutosaveName(playtestRun == nil ? "AtlasMainWindow" : "AtlasPlaytestWindow")
    do {
      if ProcessInfo.processInfo.arguments.contains("--playtest") && playtestRun == nil {
        throw NSError(domain: "Atlas", code: 1, userInfo: [NSLocalizedDescriptionKey: "A valid disposable play-test directory is required."])
      }
      if let run = playtestRun {
        dataDirectory = run.appendingPathComponent("game")
        try configurePlaytest()
      } else if let override = ProcessInfo.processInfo.environment["ATLAS_DATA_DIR"] {
        dataDirectory = URL(fileURLWithPath: override, isDirectory: true)
      } else {
        dataDirectory = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
          .appendingPathComponent("NetHack Atlas/5.0", isDirectory: true)
      }
      for mode in ["standard", "beginner", "explore", "pauper"] {
        let directory = gameDirectory(for: mode)
        try prepareGameDirectory(at: directory, mode: mode)
        let recoveries = Recovery.recoverInterruptedGames(
          in: directory, using: resources.appendingPathComponent("engine/recover"))
        for report in recoveries
        where report.disposition == .recovered || report.disposition == .failed {
          send(["type": report.disposition == .failed ? "error" : "message",
                "text": "\(mode.capitalized): \(report.detail)"])
        }
      }
      loadTilesets()
      web.loadFileURL(
        resources.appendingPathComponent("web/index.html"), allowingReadAccessTo: resources)
    } catch { showError("Could not prepare the game", error.localizedDescription) }
    window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
  }

  func configureMenu() {
    let main = NSMenu()
    let application = NSMenuItem()
    main.addItem(application)
    let appMenu = NSMenu()
    appMenu.addItem(withTitle: "About Atlas", action: #selector(about), keyEquivalent: "")
    appMenu.addItem(.separator())
    appMenu.addItem(
      withTitle: "Quit Atlas", action: #selector(NSApplication.terminate(_:)),
      keyEquivalent: "q")
    application.submenu = appMenu
    let game = NSMenuItem(title: "Game", action: nil, keyEquivalent: "")
    let gameMenu = NSMenu(title: "Game")
    gameMenu.addItem(withTitle: "Save Game", action: #selector(saveGame), keyEquivalent: "s")
    gameMenu.addItem(
      withTitle: "Show Save Folder", action: #selector(showSaveFolder), keyEquivalent: "")
    game.submenu = gameMenu
    main.addItem(game)
    let edit = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
    let editMenu = NSMenu(title: "Edit")
    for (title, selector, key) in [
      ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"),
      ("Select All", "selectAll:", "a"),
    ] {
      editMenu.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
    }
    edit.submenu = editMenu
    main.addItem(edit)
    let view = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
    let viewMenu = NSMenu(title: "View")
    viewMenu.addItem(
      withTitle: "Enter Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)),
      keyEquivalent: "f"
    ).keyEquivalentModifierMask = [.command, .control]
    view.submenu = viewMenu
    main.addItem(view)
    NSApp.mainMenu = main
  }

  // A runtime namespace keeps saves, bones, scores and checkpoint recovery
  // together without changing NetHack's save format or relocating old saves.
  func gameDirectory(for mode: String) -> URL {
    switch mode {
    case "beginner": return dataDirectory.appendingPathComponent("Beginner", isDirectory: true)
    case "explore": return dataDirectory.appendingPathComponent("Explore", isDirectory: true)
    case "pauper": return dataDirectory.appendingPathComponent("Pauper", isDirectory: true)
    default: return dataDirectory
    }
  }

  func prepareGameDirectory(at directory: URL, mode: String) throws {
    try fm.createDirectory(
      at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    let gameResources = resources.appendingPathComponent("engine")
    for file in try fm.contentsOfDirectory(at: gameResources, includingPropertiesForKeys: nil)
    where ["nhdat", "license", "symbols", "sysconf"].contains(file.lastPathComponent) {
      let destination = directory.appendingPathComponent(file.lastPathComponent)
      if !fm.fileExists(atPath: destination.path) { try fm.copyItem(at: file, to: destination) }
    }
    try fm.createDirectory(
      at: directory.appendingPathComponent("save"), withIntermediateDirectories: true)
    if mode == "explore" {
      // Authorize upstream discovery mode only in its isolated runtime.
      // Standard and Beginner keep their original sysconf and scoring rules.
      let config = directory.appendingPathComponent("sysconf")
      let original = try String(contentsOf: config, encoding: .utf8)
      let lines = original.components(separatedBy: .newlines).filter {
        $0.range(of: "^\\s*EXPLORERS\\s*=", options: .regularExpression) == nil
      }
      let updated = lines.joined(separator: "\n").trimmingCharacters(in: .newlines) + "\nEXPLORERS=*\n"
      if updated != original { try updated.write(to: config, atomically: true, encoding: .utf8) }
    }
    for name in ["record", "logfile", "xlogfile", "perm"] {
      let path = directory.appendingPathComponent(name).path
      if !fm.fileExists(atPath: path) {
        fm.createFile(atPath: path, contents: Data(), attributes: [.posixPermissions: 0o600])
      }
    }
  }

  func loadTilesets() {
    let url = resources.appendingPathComponent("assets/tiles/manifest.json")
    if let data = try? Data(contentsOf: url),
      let object = try? JSONSerialization.jsonObject(with: data)
    {
      tileManifest =
        object as? [[String: Any]] ?? (object as? [String: Any])?["tilesets"] as? [[String: Any]]
        ?? []
    }
    let imported = dataDirectory.appendingPathComponent("imported-tileset.json")
    if fm.fileExists(atPath: imported.path) {
      do {
        tileManifest.append(try TilesetImport.reload(imported).manifest)
      } catch {
        send(["type": "error", "text":
          "The saved custom tileset could not be loaded. Using bundled tiles. Your import file has been kept. \(error.localizedDescription)"])
      }
    }
    // Exercise a requested atlas in the isolated, nonpersistent native test.
    if (selfTest || playtestRun != nil), let requested = ProcessInfo.processInfo.environment["ATLAS_TEST_TILESET"],
      let index = tileManifest.firstIndex(where: { $0["id"] as? String == requested })
    {
      tileManifest.insert(tileManifest.remove(at: index), at: 0)
    }
  }

  func savedPlayers(in mode: String) -> [String] {
    let prefix = String(getuid())
    let folder = gameDirectory(for: mode).appendingPathComponent("save")
    let files =
      (try? fm.contentsOfDirectory(
        at: folder, includingPropertiesForKeys: [.contentModificationDateKey, .isRegularFileKey]))
      ?? []
    return files.filter {
      $0.lastPathComponent.hasPrefix(prefix)
        && (try? $0.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true
    }
    .sorted {
      ((try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate)
        ?? .distantPast)
        > ((try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate)
          ?? .distantPast)
    }
    .compactMap { file in
      var name = String(file.lastPathComponent.dropFirst(prefix.count))
      for suffix in [".gz", ".Z", ".NetHack-saved-game", ".svh"] {
        if name.hasSuffix(suffix) { name = String(name.dropLast(suffix.count)) }
      }
      return name.isEmpty ? nil : name
    }
  }
  var savedGames: [[String: String]] {
    ["standard", "beginner", "explore", "pauper"].flatMap { mode in
      savedPlayers(in: mode).map { ["name": $0, "mode": mode] }
    }
  }
  var hasSave: Bool { !savedGames.isEmpty }

  func boot() {
    send([
      "type": "boot", "version": "5.0.0", "tilesets": tileManifest, "hasSave": hasSave,
      "selfTest": selfTest, "savedGames": savedGames, "playtest": playtestSummary as Any? ?? NSNull(),
      "testGender": selfTest ? (ProcessInfo.processInfo.environment["ATLAS_TEST_GENDER"] ?? "female") : "",
      "testMode": selfTest ? (ProcessInfo.processInfo.environment["ATLAS_TEST_MODE"] ?? "standard") : "",
      "testNudist": selfTest && ProcessInfo.processInfo.environment["ATLAS_TEST_NUDIST"] == "1",
      "testBlind": selfTest && ProcessInfo.processInfo.environment["ATLAS_TEST_BLIND"] == "1",
      "testDeaf": selfTest && ProcessInfo.processInfo.environment["ATLAS_TEST_DEAF"] == "1",
      "testNoStartingPet": selfTest && ProcessInfo.processInfo.environment["ATLAS_TEST_NO_STARTING_PET"] == "1",
      "testScenario": selfTest ? (ProcessInfo.processInfo.environment["ATLAS_TEST_SCENARIO"] ?? "") : "",
      "testRoomBounds": selfTest ? (ProcessInfo.processInfo.environment["ATLAS_TEST_ROOM_BOUNDS"] ?? "") : "",
      "testTerrainTiles": selfTest ? (ProcessInfo.processInfo.environment["ATLAS_TEST_TERRAIN_TILES"] ?? "[]") : "[]",
      "name": preferences.string(forKey: "lastCharacterName") ?? "Adventurer",
    ])
  }

  func userContentController(
    _ userContentController: WKUserContentController, didReceive message: WKScriptMessage
  ) {
    if selfTest {
      NSLog(
        "Atlas bridge %@ %@", String(describing: message.frameInfo.request.url),
        String(describing: message.body))
    }
    guard message.frameInfo.isMainFrame, message.frameInfo.request.url?.isFileURL == true,
      let body = message.body as? [String: Any], let action = body["action"] as? String
    else { return }
    switch action {
    case "ready":
      ready = true
      boot()
      flush()
      if playtestRun != nil && !playtestAutoStarted {
        playtestAutoStarted = true
        launch(["mode": "standard"], restoring: true)
      }
      if selfTest {
        DispatchQueue.main.asyncAfter(deadline: .now() + 35) { [weak self] in
          guard let self, self.engine != nil else { return }
          self.web.takeSnapshot(with: nil) { image, _ in
            if let image, let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]),
              let path = ProcessInfo.processInfo.environment["ATLAS_SNAPSHOT"]
            {
              try? png.write(to: URL(fileURLWithPath: path))
            }
          }
          NSLog("Atlas smoke-test watchdog: current input %@", self.currentInput)
          self.write("save")
        }
      }
    case "diagnostic":
      guard selfTest else { return }
      if let url = diagnosticsURL,
        let data = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys])
      {
        if !fm.fileExists(atPath: url.path) { fm.createFile(atPath: url.path, contents: nil) }
        if let file = try? FileHandle(forWritingTo: url) {
          _ = try? file.seekToEnd()
          try? file.write(contentsOf: data + Data([10]))
          try? file.close()
        }
      }
      let snapshotNames = ["room-shape": "room-shape.png", "oracle-minor-prompt": "oracle-minor.png", "oracle-major-prompt": "oracle-major.png", "oracle-reading": "oracle-reading.png",
                           "court-beneath": "court-beneath.png", "yn-default-focus": "yn-default.png", "direction-bar": "direction.png", "actions-filter": "actions.png",
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
                           "lantern-bars-blocked": "lantern-bars-blocked.png"]
      if let phase = body["phase"] as? String, let filename = snapshotNames[phase] {
        self.web.takeSnapshot(with: nil) { image, _ in
          if let image, let tiff = image.tiffRepresentation,
            let rep = NSBitmapImageRep(data: tiff),
            let png = rep.representation(using: .png, properties: [:]),
            let path = ProcessInfo.processInfo.environment["ATLAS_SNAPSHOT"]
          {
            let destination = URL(fileURLWithPath: path).deletingLastPathComponent().appendingPathComponent(filename)
            try? png.write(to: destination)
          }
        }
      }
      if body["phase"] as? String == "complete" {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
          self.web.takeSnapshot(with: nil) { image, _ in
            if let image, let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]),
              let path = ProcessInfo.processInfo.environment["ATLAS_SNAPSHOT"]
            {
              try? png.write(to: URL(fileURLWithPath: path))
            }
            NSApp.terminate(nil)
          }
        }
      }
    case "start", "load": launch(body, restoring: action == "load")
    case "key":
      if let number = body["key"] as? Int {
        write("key \(number)")
      } else if let key = body["key"] as? String {
        sendKey(key)
      }
    case "command":
      if let name = body["name"] as? String, !name.isEmpty, name.utf8.count < 80,
        !name.contains("\n"), !name.contains("\r"), !name.contains("\0") {
        write("command \(name)")
      }
    case "input":
      let text = String((body["text"] as? String ?? "").prefix(240)).replacingOccurrences(
        of: "\n", with: " "
      ).replacingOccurrences(of: "\r", with: " ")
      write("line \(text)")
    case "position":
      if let x = body["x"] as? Int, let y = body["y"] as? Int,
        (1..<80).contains(x), (0..<21).contains(y) {
        write("position \(x) \(y)")
      }
    case "menu":
      if body["cancelled"] as? Bool == true || body["cancel"] as? Bool == true {
        write("menu cancel")
      } else if let selections = body["selections"] as? [[String: Any]] {
        let ids = selections.compactMap { entry -> String? in
          guard let id = entry["id"] as? Int else { return nil }
          let count = entry["count"] as? Int ?? -1
          return "\(id):\(count)"
        }
        write("menu " + ids.joined(separator: ","))
      }
    case "inspect":
      if let x = body["x"] as? Int, let y = body["y"] as? Int, (0..<80).contains(x),
        (0..<21).contains(y)
      {
        write("inspect \(x) \(y)")
      }
    case "save": saveGame()
    case "importTileset": importTileset(body)
    case "showSaveFolder": showSaveFolder()
    default: break
    }
  }

  func launch(_ options: [String: Any], restoring: Bool) {
    guard engine == nil else {
      send(["type": "error", "text": "Save the current expedition before starting another."])
      return
    }
    let mode = options["mode"] as? String ?? "standard"
    guard ["standard", "beginner", "explore", "pauper"].contains(mode) else {
      send(["type": "error", "text": "Choose Standard, Beginner, Explore or Pauper for this adventure."])
      return
    }
    playtestRestoring = playtestRun != nil && restoring
    let available = savedPlayers(in: mode)
    if restoring && available.isEmpty {
      send(["type": "error", "text": "There is no saved adventure to continue."])
      return
    }
    let requested = options["name"] as? String
    if restoring, let requested, !available.contains(requested) {
      send(["type": "error", "text": "That saved adventure is no longer available."])
      return
    }
    let rawName =
      restoring
      ? (requested.flatMap { available.contains($0) ? $0 : nil } ?? available.first ?? "Adventurer")
      : requested ?? "Adventurer"
    let sanitized = String(
      rawName.unicodeScalars.filter {
        $0.isASCII && (CharacterSet.alphanumerics.contains($0) || $0 == "_")
      }.prefix(
        24))
    playerName = restoring ? rawName : (sanitized.isEmpty ? "Adventurer" : sanitized)
    if !restoring
      && available.contains(where: { $0.caseInsensitiveCompare(playerName) == .orderedSame })
    {
      send([
        "type": "error",
        "text":
          "An adventure named \(playerName) is already saved. Continue that adventure or use a different name.",
      ])
      return
    }
    preferences.set(playerName, forKey: "lastCharacterName")
    playMode = mode
    let directory = gameDirectory(for: mode)
    let process = Process()
    process.executableURL = resources.appendingPathComponent("engine/nethack")
    process.currentDirectoryURL = directory
    var arguments = ["-u", playerName, "-@"]
    if mode == "explore" { arguments.append("-X") }
    if !restoring {
      for (name, flag) in [("role", "-p"), ("race", "-r")] {
        if let value = options[name] as? String, !value.isEmpty, value.lowercased() != "random" {
          arguments += [flag, String(value.prefix(30))]
        }
      }
    }
    process.arguments = arguments
    var environment = ProcessInfo.processInfo.environment
    environment["NETHACKDIR"] = directory.path
    environment["HACKDIR"] = directory.path
    environment["HOME"] = directory.path
    environment["ATLAS_PLAY_MODE"] = mode
    environment["TERM"] = "dumb"
    var gameOptions = ["color", "hilite_pet", "!autopickup", "time", "!news",
                       "force_invmenu", "menustyle:full"]
    if selfTest, let keypad = environment["ATLAS_TEST_NUMBER_PAD"],
      ["0", "1", "3"].contains(keypad) {
      gameOptions.append("number_pad:\(keypad)")
    }
    if !restoring {
      if mode == "pauper" { gameOptions.append("pauper") }
      if mode != "pauper" && options["nudist"] as? Bool == true {
        gameOptions.append("nudist")
      }
      if options["blind"] as? Bool == true { gameOptions.append("blind") }
      if options["deaf"] as? Bool == true { gameOptions.append("deaf") }
      if options["noStartingPet"] as? Bool == true { gameOptions.append("pettype:none") }
      for (field, option) in [("gender", "gender"), ("alignment", "align")] {
        if let value = options[field] as? String, !value.isEmpty, value.lowercased() != "random",
          value.allSatisfy({ $0.isLetter })
        {
          gameOptions.append("\(option):\(value)")
        }
      }
    }
    environment["NETHACKOPTIONS"] = gameOptions.joined(separator: ",")
    process.environment = environment
    let stdinPipe = Pipe()
    let stdoutPipe = Pipe()
    let stderrPipe = Pipe()
    process.standardInput = stdinPipe
    process.standardOutput = stdoutPipe
    process.standardError = stderrPipe
    input = stdinPipe.fileHandleForWriting
    readPipe = stdoutPipe
    errorPipe = stderrPipe
    pending = Data()
    stderrTail = ""
    closing = false
    for pipe in [stdoutPipe, stderrPipe] {
      let fd = pipe.fileHandleForReading.fileDescriptor
      _ = fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK)
    }
    do {
      engine = process
      try process.run()
      if selfTest { NSLog("Atlas engine pid %d", process.processIdentifier) }
      send(["type": "started", "name": playerName, "mode": mode])
      let timer = Timer(timeInterval: 0.016, repeats: true) { [weak self] _ in self?.pumpEngine() }
      ioTimer = timer
      RunLoop.main.add(timer, forMode: .common)
    } catch {
      engine = nil
      input = nil
      if selfTest { NSLog("Atlas engine launch failed %@", error.localizedDescription) }
      send(["type": "error", "text": error.localizedDescription])
    }
  }

  func pumpEngine() {
    guard let process = engine else { return }
    var buffer = [UInt8](repeating: 0, count: 65536)
    for (pipe, isOutput) in [(readPipe, true), (errorPipe, false)] {
      guard let pipe else { continue }
      for _ in 0..<64 {
        let count = read(pipe.fileHandleForReading.fileDescriptor, &buffer, buffer.count)
        if count <= 0 { break }
        let data = Data(buffer.prefix(count))
        if isOutput {
          consume(data)
        } else {
          stderrTail = String((stderrTail + String(decoding: data, as: UTF8.self)).suffix(8000))
        }
      }
    }
    if !process.isRunning {
      ioTimer?.invalidate()
      ioTimer = nil
      input = nil
      engine = nil
      readPipe = nil
      errorPipe = nil
      var completion: [String: Any] = [
        "type": "exit", "code": process.terminationStatus, "hasSave": hasSave, "detail": stderrTail,
        "savedGames": savedGames,
      ]
      if reportDestination != nil && process.terminationStatus == 0 && hasSave {
        completion["reason"] = "playtest-report"
      }
      send(completion)
      boot()
      if reportDestination != nil { finishPlaytestReport() }
      if closing { NSApp.reply(toApplicationShouldTerminate: true) }
    }
  }

  func consume(_ data: Data) {
    pending.append(data)
    while let end = pending.firstIndex(of: 10) {
      let line = pending.prefix(upTo: end)
      pending.removeSubrange(...end)
      if playtestRun != nil || (selfTest && ProcessInfo.processInfo.environment["ATLAS_DIAGNOSTICS"] != nil) {
        let trace = playtestRun?.appendingPathComponent("engine.jsonl").path ?? (ProcessInfo.processInfo.environment["ATLAS_DIAGNOSTICS"]! + ".engine.jsonl")
        if !fm.fileExists(atPath: trace) { fm.createFile(atPath: trace, contents: nil) }
        if let handle = FileHandle(forWritingAtPath: trace) {
          _ = try? handle.seekToEnd()
          try? handle.write(contentsOf: Data(line) + Data([10]))
          try? handle.close()
        }
      }
      if let object = try? JSONSerialization.jsonObject(with: line),
        let event = object as? [String: Any]
      {
        if event["type"] as? String == "input" { currentInput = event["kind"] as? String ?? "" }
        if playtestRestoring, event["type"] as? String == "input",
          event["kind"] as? String == "yn",
          event["prompt"] as? String == "Do you want to keep the save file?" {
          // Only discard the resumed working copy. The pristine checkpoint is separate.
          write("key 110")
          continue
        }
        if event["type"] as? String == "input", event["command"] as? Bool == true { playtestRestoring = false }
        if reportDestination != nil && event["type"] as? String == "exit" {
          var transition = event
          transition["reason"] = "playtest-report"
          send(transition)
        } else { send(event) }
        driveLivePlaytest(event)
      } else if !line.isEmpty {
        stderrTail = String(
          (stderrTail + String(decoding: line, as: UTF8.self) + "\n").suffix(8000))
      }
    }
    if pending.count > 8 * 1024 * 1024 {
      pending.removeAll()
      send(["type": "error", "text": "The game returned an oversized message."])
    }
  }
  func send(_ event: [String: Any]) {
    events.append(event)
    if ready && !flushScheduled {
      flushScheduled = true
      DispatchQueue.main.asyncAfter(deadline: .now() + 0.016) { self.flush() }
    }
  }
  func flush() {
    flushScheduled = false
    guard ready, !events.isEmpty else { return }
    let batch = events
    events.removeAll()
    guard let data = try? JSONSerialization.data(withJSONObject: batch),
      let json = String(data: data, encoding: .utf8)
    else { return }
    web.evaluateJavaScript("\(json).forEach(function(e){window.receiveNative(e);});") { _, error in
      if let error { NSLog("Atlas UI: %@", error.localizedDescription) }
    }
  }
  func write(_ command: String) {
    guard let input, engine?.isRunning == true, let bytes = (command + "\n").data(using: .utf8)
    else { return }
    do { try input.write(contentsOf: bytes) } catch {
      send(["type": "error", "text": "The game connection closed: \(error.localizedDescription)"])
    }
  }
  func sendKey(_ key: String) {
    let keys: [String: Int] = [
      "ArrowUp": 107, "ArrowDown": 106, "ArrowLeft": 104, "ArrowRight": 108, "Enter": 10,
      "Return": 10, "Escape": 27, "Backspace": 8, "Tab": 9, "Space": 32,
    ]
    if let code = keys[key] {
      write("key \(code)")
    } else if key.utf8.count == 1, let code = key.utf8.first {
      write("key \(code)")
    }
  }
  @objc func saveGame() {
    if playtestLiveDestination != nil { closePlaytest(); return }
    if engine != nil { write("save") }
  }
  @objc func showSaveFolder() {
    NSWorkspace.shared.open(engine == nil ? dataDirectory : gameDirectory(for: playMode))
  }
  @objc func about() {
    let alert = NSAlert()
    alert.messageText = "Atlas for NetHack"
    alert.informativeText =
      "An independent, offline macOS interface for NetHack 5.0.0.\n\nAtlas is not affiliated with or endorsed by the NetHack Development Team.\n\nNetHack © 1985-2026 Stichting Mathematisch Centrum and M. Stephenson.\nEngine, tileset credits, license and matching source are included inside the application."
    alert.runModal()
  }
  func showError(_ title: String, _ detail: String) {
    let alert = NSAlert()
    alert.messageText = title
    alert.informativeText = detail
    alert.runModal()
  }

  func importTileset(_ body: [String: Any]) {
    let panel = NSOpenPanel()
    panel.allowedContentTypes = [.png, .bmp]
    panel.allowsMultipleSelection = false
    panel.message =
      "Choose a NetHack 5.0 tilesheet. Set its tile size in Display settings after import."
    panel.beginSheetModal(for: window) { response in
      guard response == .OK, let url = panel.url else { return }
      do {
        let width = try TilesetImport.integer(body["tileWidth"] ?? 32)
        let height = try TilesetImport.integer(body["tileHeight"] ?? 32)
        let imported = try TilesetImport.convert(url, tileWidth: width, tileHeight: height)
        try TilesetImport.persist(imported, to: self.dataDirectory.appendingPathComponent("imported-tileset.json"))
        self.tileManifest.removeAll { $0["id"] as? String == "custom" }
        self.tileManifest.append(imported.manifest)
        self.send(["type": "tilesetImported", "tileset": imported.manifest, "persistent": true])
      } catch {
        self.send([
          "type": "error", "text": "The tileset could not be imported. Your previous import is unchanged. \(error.localizedDescription)",
        ])
      }
    }
  }
  func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
    if reportDestination != nil { return .terminateCancel }
    guard engine?.isRunning == true else { return .terminateNow }
    if playtestLiveDestination != nil, let engine {
      // Only disposable live tutorials: upstream intentionally cannot save them.
      kill(engine.processIdentifier, SIGKILL)
      engine.waitUntilExit()
      return .terminateNow
    }
    closing = true
    write("save")
    DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
      guard self.closing, self.engine?.isRunning == true else { return }
      self.closing = false
      NSApp.reply(toApplicationShouldTerminate: false)
      self.send([
        "type": "error",
        "text":
          "Finish the current game prompt, then save and quit again. Your game is still running.",
      ])
    }
    return .terminateLater
  }
  func windowShouldClose(_ sender: NSWindow) -> Bool {
    NSApp.terminate(nil)
    return false
  }
  func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
  func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
    if selfTest { NSLog("Atlas loaded %@", webView.url?.absoluteString ?? "nil") }
  }
  func webView(
    _ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
    withError error: Error
  ) { NSLog("Atlas page failed: %@", error.localizedDescription) }
  func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
    // The renderer cannot reliably display its own termination notice. Native
    // Game > Save Game still writes directly to the live engine's input pipe.
    let alert = NSAlert()
    alert.messageText = "The display process stopped"
    alert.informativeText = engine?.isRunning == true
      ? "Use Game > Save Game before reopening Atlas. Your game continues running until it is saved."
      : "Reopen Atlas to restore the display."
    alert.addButton(withTitle: "OK")
    alert.beginSheetModal(for: window)
  }
  func webView(
    _ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
    decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
  ) {
    guard let url = navigationAction.request.url, url.isFileURL,
      url.standardizedFileURL.path.hasPrefix(resources.standardizedFileURL.path + "/")
    else {
      decisionHandler(.cancel)
      return
    }
    decisionHandler(.allow)
  }
}
@main
struct AtlasMain {
  static func main() {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.delegate = delegate
    withExtendedLifetime(delegate) { app.run() }
  }
}
