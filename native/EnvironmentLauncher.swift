import Cocoa

// A workspace development tool, deliberately separate from the player application.
final class EnvironmentLauncher: NSObject, NSApplicationDelegate, NSWindowDelegate {
  let fm = FileManager.default
  var window: NSWindow!
  let environment = NSPopUpButton(), variant = NSPopUpButton(), tileset = NSPopUpButton(), mode = NSPopUpButton()
  let detail = NSTextField(wrappingLabelWithString: "")
  let status = NSTextField(wrappingLabelWithString: "Choose an environment, then Play. You can explore freely in the actual game.")
  var cases = [[String: Any]](), variants = [[String: Any]](), tileChoices = [[String: String]]()
  var buttons = [NSButton]()
  var game: Process?
  var run: URL?
  var busy = false
  var lock: Int32 = -1
  let root: URL = {
    let url = Bundle.main.resourceURL!.appendingPathComponent("workspace.txt")
    return URL(fileURLWithPath: (try! String(contentsOf: url, encoding: .utf8)).trimmingCharacters(in: .whitespacesAndNewlines))
  }()
  var base: URL { root.appendingPathComponent(".artifacts/environment-playtests") }
  var app: URL { root.appendingPathComponent("dist/Atlas.app") }

  func applicationDidFinishLaunching(_ notification: Notification) {
    NSApp.setActivationPolicy(.regular); NSApp.appearance = NSAppearance(named: .darkAqua)
    do { try fm.createDirectory(at: base, withIntermediateDirectories: true) }
    catch { fail(error.localizedDescription); return }
    lock = open(base.appendingPathComponent("launcher.lock").path, O_CREAT | O_RDWR | O_CLOEXEC, 0o600)
    guard lock >= 0, flock(lock, LOCK_EX | LOCK_NB) == 0 else { fail("The environment launcher is already open."); NSApp.terminate(nil); return }
    let menu = NSMenu(); let item = NSMenuItem(); let submenu = NSMenu()
    submenu.addItem(withTitle: "Quit Environment Launcher", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
    item.submenu = submenu; menu.addItem(item)
    let edit = NSMenuItem(); edit.title = "Edit"; let editMenu = NSMenu(title: "Edit")
    for (title, action, key) in [("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
      editMenu.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
    }
    edit.submenu = editMenu; menu.addItem(edit); NSApp.mainMenu = menu
    window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 610), styleMask: [.titled,.closable,.miniaturizable], backing: .buffered, defer: false)
    window.title = "Atlas Environment Playtests"; window.delegate = self
    let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 18
    stack.translatesAutoresizingMaskIntoConstraints = false; window.contentView!.addSubview(stack)
    NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 28),
      stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -28),
      stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 28)])
    let title = NSTextField(labelWithString: "Explore every environment")
    title.font = .systemFont(ofSize: 25, weight: .semibold); stack.addArrangedSubview(title)
    let intro = NSTextField(wrappingLabelWithString: "Real NetHack. Disposable saves. Current shipped artwork. Regional concept art is not yet in the game.")
    stack.addArrangedSubview(intro)
    for (label, control) in [("Environment",environment),("Layout",variant),("Tileset",tileset),("Test mode",mode)] {
      let row = NSStackView(); row.orientation = .horizontal; row.spacing = 16
      let text = NSTextField(labelWithString: label); text.widthAnchor.constraint(equalToConstant: 110).isActive = true
      control.widthAnchor.constraint(equalToConstant: 500).isActive = true
      row.addArrangedSubview(text); row.addArrangedSubview(control); stack.addArrangedSubview(row)
    }
    environment.target = self; environment.action = #selector(changeEnvironment)
    variant.target = self; variant.action = #selector(changeDetails)
    mode.addItems(withTitles: ["Exploration: normal visibility and encounters", "Inspection: revealed map and protection"])
    mode.target = self; mode.action = #selector(changeDetails)
    do {
      let data = try Data(contentsOf: app.appendingPathComponent("Contents/Resources/assets/tiles/manifest.json"))
      guard let manifest = try JSONSerialization.jsonObject(with: data) as? [String: Any],
        let entries = manifest["tilesets"] as? [[String: Any]], !entries.isEmpty else {
        throw NSError(domain: "Atlas", code: 1, userInfo: [NSLocalizedDescriptionKey: "The built app has no tilesets."])
      }
      tileChoices = try entries.map { entry in
        guard let id = entry["id"] as? String, let name = entry["name"] as? String else {
          throw NSError(domain: "Atlas", code: 1, userInfo: [NSLocalizedDescriptionKey: "A built tileset is missing its name or ID."])
        }
        return ["id": id, "name": name]
      }
      tileset.addItems(withTitles: tileChoices.map { $0["name"]! })
      if let index = tileChoices.firstIndex(where: { $0["id"] == "lantern-modern" }) { tileset.selectItem(at: index) }
    } catch { fail("Build Atlas before opening the play-test launcher. \(error.localizedDescription)"); return }
    detail.textColor = .secondaryLabelColor; detail.preferredMaxLayoutWidth = 690
    stack.addArrangedSubview(detail)
    let actions = NSStackView(); actions.orientation = .horizontal; actions.spacing = 10
    for (title, selector) in [("Play",#selector(play)),("Resume Last Test",#selector(resume)),("Reset Test",#selector(reset)),("Show Reports",#selector(reports))] {
      let button = NSButton(title: title, target: self, action: selector); buttons.append(button); actions.addArrangedSubview(button)
    }
    stack.addArrangedSubview(actions)
    status.preferredMaxLayoutWidth = 690; stack.addArrangedSubview(status)
    let help = NSTextField(wrappingLabelWithString: "In the game, use Play-test → Report Problem to capture a screenshot and save. Save & close to return here. Reset starts a fresh copy of the same layout; earlier tests are retained. These debug games never affect your real saves or scores.")
    help.textColor = .secondaryLabelColor; stack.addArrangedSubview(help)
    window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    helper(["catalog"]) { data in
      guard let entries = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else { self.fail("The environment catalog could not be read."); return }
      self.cases = entries
      self.environment.addItems(withTitles: Array(Set(entries.compactMap { $0["group"] as? String })).sorted())
      self.environment.selectItem(withTitle: "Mines"); self.changeEnvironment()
      if let data = try? Data(contentsOf: self.base.appendingPathComponent("last-session.json")),
        let saved = try? JSONSerialization.jsonObject(with: data) as? [String: String], let path = saved["run"] {
        self.run = URL(fileURLWithPath: path)
      }
      if ProcessInfo.processInfo.arguments.contains("--self-test") { self.verifyLauncher() }
    }
  }
  func verifyLauncher() {
    try? fm.removeItem(at: base.appendingPathComponent("launcher-check.json"))
    try? fm.removeItem(at: base.appendingPathComponent("launcher-check-error.txt"))
    environment.selectItem(withTitle: "Mines"); changeEnvironment()
    mode.selectItem(at: 1); changeDetails()
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
      if let image = CGWindowListCreateImage(.null, .optionIncludingWindow, CGWindowID(self.window.windowNumber), [.boundsIgnoreFraming, .bestResolution]) {
        let bitmap = NSBitmapImageRep(cgImage: image)
        try? bitmap.representation(using: .png, properties: [:])?.write(to: self.base.appendingPathComponent("launcher.png"))
      }
      self.buttons[0].performClick(nil)
    }
    var stage = 0; var firstRun: URL?; var readyAt: Date?
    let deadline = Date().addingTimeInterval(90)
    Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { timer in
      if Date() > deadline {
        timer.invalidate()
        try? Data("Launcher verification timed out at stage \(stage)".utf8).write(to: self.base.appendingPathComponent("launcher-check-error.txt"))
        self.stopThen { NSApp.terminate(nil) }; return
      }
      guard !self.busy, let run = self.run, self.game?.isRunning == true,
        let trace = try? String(contentsOf: run.appendingPathComponent("engine.jsonl"), encoding: .utf8), trace.contains("\"command\":true") else { return }
      if stage == 0 {
        if readyAt == nil { readyAt = Date().addingTimeInterval(2) }
        guard Date() > readyAt! else { return }
        firstRun = run; stage = 1
        try? Data("{\"action\":\"report\",\"notes\":\"Launcher button integration check\"}".utf8).write(to: run.appendingPathComponent("request.json"), options: .atomic)
      } else if stage == 1 && self.fm.fileExists(atPath: run.appendingPathComponent("report-status.json").path) {
        stage = 2; self.buttons[2].performClick(nil)
      } else if stage == 2 && run != firstRun {
        stage = 3; timer.invalidate()
        let result = ["passed":true,"firstRun":firstRun!.path,"resetRun":run.path] as [String:Any]
        try? JSONSerialization.data(withJSONObject: result).write(to: self.base.appendingPathComponent("launcher-check.json"))
        self.stopThen { NSApp.terminate(nil) }
      }
    }
  }
  func fail(_ message: String) {
    status.stringValue = message
    let alert = NSAlert(); alert.messageText = "Play-test could not continue"; alert.informativeText = message; alert.runModal()
  }
  func setBusy(_ value: Bool) {
    busy = value
    for control in [environment,variant,tileset,mode] { control.isEnabled = !value }
    for button in buttons { button.isEnabled = !value }
  }
  @objc func changeEnvironment() {
    variants = cases.filter { $0["group"] as? String == environment.titleOfSelectedItem }
    variant.removeAllItems(); variant.addItems(withTitles: variants.compactMap { $0["label"] as? String }); changeDetails()
  }
  @objc func changeDetails() {
    guard variants.indices.contains(variant.indexOfSelectedItem) else { return }
    let entry = variants[variant.indexOfSelectedItem]
    let kind = entry["source"] is String || entry["room"] != nil || entry["terrain"] != nil ? "Targeted engine layout in its branch." : "Generated world, direct arrival at the chosen level."
    if entry["group"] as? String == "Tutorial" {
      detail.stringValue = "Live scripted tutorial. NetHack forbids tutorial saves: Reset restarts it, and reports capture the screen and trace. Resume restarts at the entrance."
      return
    }
    detail.stringValue = kind + (mode.indexOfSelectedItem == 0 ? " No map reveal or protection added. Debug death refusal is available." : " Map revealed; timed resistances and a digging wand supplied. Monsters remain active. Protection is not invulnerability.")
  }
  var tileID: String { tileChoices[max(0,tileset.indexOfSelectedItem)]["id"]! }
  func helper(_ arguments: [String], complete: @escaping (Data) -> Void) {
    setBusy(true)
    DispatchQueue.global().async {
      let process = Process(); process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
      process.arguments = [self.root.appendingPathComponent("scripts/playtest/prepare.py").path] + arguments
      process.currentDirectoryURL = self.root
      let output = Pipe(); process.standardOutput = output
      // Drain stderr concurrently so a diagnostic cannot block the helper.
      let errorURL = self.base.appendingPathComponent("last-preparation-error.txt")
      self.fm.createFile(atPath: errorURL.path, contents: nil)
      let errorFile = try? FileHandle(forWritingTo: errorURL); process.standardError = errorFile
      do {
        try process.run(); let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit(); try? errorFile?.close()
        DispatchQueue.main.async {
          self.setBusy(false)
          if process.terminationStatus == 0 { complete(data) }
          else { self.fail((try? String(contentsOf: errorURL, encoding: .utf8)) ?? "Checkpoint preparation failed. See the test files.") }
        }
      } catch { DispatchQueue.main.async { self.setBusy(false); self.fail(error.localizedDescription) } }
    }
  }
  func stopThen(_ continuation: @escaping () -> Void) {
    guard let game, game.isRunning, let run else { continuation(); return }
    setBusy(true); status.stringValue = "Saving the current test before switching…"
    do { try Data("{\"action\":\"close\"}".utf8).write(to: run.appendingPathComponent("request.json"), options: .atomic) }
    catch { setBusy(false); fail(error.localizedDescription); return }
    let deadline = Date().addingTimeInterval(15)
    Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { timer in
      if !game.isRunning { timer.invalidate(); self.setBusy(false); continuation() }
      else if Date() > deadline { timer.invalidate(); self.setBusy(false); self.fail("The game is still open. Finish its prompt and close it, then try again. Nothing was reset.") }
    }
  }
  @objc func play() {
    guard variants.indices.contains(variant.indexOfSelectedItem), let id = variants[variant.indexOfSelectedItem]["id"] as? String else { return }
    let selectedMode = mode.indexOfSelectedItem == 0 ? "exploration" : "inspection"
    stopThen {
      self.status.stringValue = "Preparing a real NetHack checkpoint…"
      self.helper(["prepare","--case",id,"--mode",selectedMode]) { data in
        guard let result = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let path = result["run"] as? String else { self.fail("Checkpoint preparation returned no game."); return }
        self.run = URL(fileURLWithPath: path); self.launch()
      }
    }
  }
  @objc func resume() {
    guard let game, game.isRunning else { if run != nil { launch() } else { status.stringValue = "Play a test first." }; return }
    NSRunningApplication(processIdentifier: game.processIdentifier)?.activate(options: .activateIgnoringOtherApps)
  }
  @objc func reset() {
    guard let run, let data = try? Data(contentsOf: run.appendingPathComponent("metadata.json")),
      let metadata = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
      let checkpoint = metadata["checkpoint"] as? String else { status.stringValue = "Play a test first."; return }
    stopThen {
      do {
        let newRun = self.base.appendingPathComponent("runs/" + UUID().uuidString)
        try self.fm.createDirectory(at: newRun, withIntermediateDirectories: true)
        try self.fm.copyItem(at: URL(fileURLWithPath: checkpoint).appendingPathComponent("game"), to: newRun.appendingPathComponent("game"))
        try data.write(to: newRun.appendingPathComponent("metadata.json"))
        self.run = newRun; self.launch()
      } catch { self.fail(error.localizedDescription) }
    }
  }
  @objc func reports() {
    let folder = run?.appendingPathComponent("reports") ?? base
    NSWorkspace.shared.open(fm.fileExists(atPath: folder.path) ? folder : (run ?? base))
  }
  func launch() {
    guard let run else { return }
    guard fm.fileExists(atPath: run.appendingPathComponent("game/save").path) else { fail("The last test files are no longer available."); return }
    let process = Process(); process.executableURL = app.appendingPathComponent("Contents/MacOS/NetHackAtlas")
    process.arguments = ["--playtest"]
    var env = ProcessInfo.processInfo.environment
    env.removeValue(forKey: "ATLAS_DATA_DIR"); env.removeValue(forKey: "ATLAS_TEST_SCENARIO")
    env["ATLAS_PLAYTEST_RUN"] = run.path; env["ATLAS_TEST_TILESET"] = tileID
    process.environment = env
    do {
      try JSONSerialization.data(withJSONObject: ["run":run.path]).write(to: base.appendingPathComponent("last-session.json"), options: .atomic)
      try? fm.removeItem(at: run.appendingPathComponent("request.json"))
      try process.run(); game = process
      status.stringValue = "Test opened. Explore freely. Use the game’s Play-test menu to report a problem or save and return."
    } catch { fail(error.localizedDescription) }
  }
  func windowShouldClose(_ sender: NSWindow) -> Bool { NSApp.terminate(nil); return false }
  func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
    if busy { status.stringValue = "Please wait for preparation or saving to finish."; return .terminateCancel }
    if let game, game.isRunning {
      stopThen { NSApp.terminate(nil) }; return .terminateCancel
    }
    return .terminateNow
  }
}
@main struct LauncherMain {
  static func main() {
    let app = NSApplication.shared; let delegate = EnvironmentLauncher(); app.delegate = delegate
    withExtendedLifetime(delegate) { app.run() }
  }
}
