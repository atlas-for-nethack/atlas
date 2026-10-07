import Cocoa
import WebKit
import CryptoKit

// Explicit development launch only. Ordinary games never watch a control file.
extension AppDelegate {
  var playtestSummary: [String: String]? {
    guard let run = playtestRun, let data = try? Data(contentsOf: run.appendingPathComponent("metadata.json")),
      let metadata = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
      let item = metadata["case"] as? [String: Any] else { return nil }
    return ["label": "\(item["group"] as? String ?? "") / \(item["label"] as? String ?? "")",
            "mode": metadata["mode"] as? String ?? "exploration"]
  }
  var playtestRun: URL? {
    guard ProcessInfo.processInfo.arguments.contains("--playtest"),
      let path = ProcessInfo.processInfo.environment["ATLAS_PLAYTEST_RUN"] else { return nil }
    let url = URL(fileURLWithPath: path).resolvingSymlinksInPath()
    guard url.deletingLastPathComponent().lastPathComponent == "runs",
      url.deletingLastPathComponent().deletingLastPathComponent().lastPathComponent == "environment-playtests",
      fm.fileExists(atPath: url.appendingPathComponent("metadata.json").path) else { return nil }
    return url
  }

  func configurePlaytest() throws {
    guard let run = playtestRun else { return }
    let lock = run.appendingPathComponent("owner.lock")
    playtestLock = open(lock.path, O_CREAT | O_RDWR | O_CLOEXEC, 0o600)
    guard playtestLock >= 0, flock(playtestLock, LOCK_EX | LOCK_NB) == 0 else {
      throw NSError(domain: "Atlas", code: 1, userInfo: [NSLocalizedDescriptionKey: "This test game is already open."])
    }
    let metadataURL = run.appendingPathComponent("metadata.json")
    var metadata = (try JSONSerialization.jsonObject(with: Data(contentsOf: metadataURL))) as! [String: Any]
    let engineHash = SHA256.hash(data: try Data(contentsOf: resources.appendingPathComponent("engine/nethack"))).map { String(format: "%02x", $0) }.joined()
    guard metadata["engine"] as? String == engineHash else {
      throw NSError(domain: "Atlas", code: 2, userInfo: [NSLocalizedDescriptionKey: "This checkpoint belongs to a different engine build. Prepare a new test."])
    }
    metadata["runningApp"] = SHA256.hash(data: try Data(contentsOf: Bundle.main.executableURL!)).map { String(format: "%02x", $0) }.joined()
    metadata["runningArtwork"] = SHA256.hash(data: try Data(contentsOf: resources.appendingPathComponent("assets/tiles/manifest.json"))).map { String(format: "%02x", $0) }.joined()
    try JSONSerialization.data(withJSONObject: metadata, options: [.prettyPrinted,.sortedKeys]).write(to: metadataURL, options: .atomic)
    if let destination = metadata["liveDestination"] as? String {
      playtestLiveDestination = destination
      if let checkpoint = metadata["checkpoint"] as? String {
        // Tutorial progress cannot be restored by upstream. Each launch uses a new entrance copy.
        let abandoned = run.appendingPathComponent("tutorial-attempt-" + UUID().uuidString)
        try fm.moveItem(at: run.appendingPathComponent("game"), to: abandoned)
        try fm.copyItem(at: URL(fileURLWithPath: checkpoint).appendingPathComponent("game"), to: run.appendingPathComponent("game"))
      }
    }
    window.title = "Environment play-test (disposable game)"
    window.titleVisibility = .visible
    let menu = NSMenu(title: "Play-test")
    menu.addItem(withTitle: "Report Problem…", action: #selector(reportPlaytest), keyEquivalent: "r")
    menu.addItem(withTitle: "Show Test Files", action: #selector(showPlaytest), keyEquivalent: "")
    menu.addItem(withTitle: "Save and Return to Launcher", action: #selector(closePlaytest), keyEquivalent: "")
    let item = NSMenuItem(); item.submenu = menu; NSApp.mainMenu?.addItem(item)
    playtestTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
      guard let self else { return }
      let request = run.appendingPathComponent("request.json")
      guard let data = try? Data(contentsOf: request),
        let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
      try? self.fm.removeItem(at: request)
      switch body["action"] as? String {
      case "close": self.closePlaytest()
      case "report": self.capturePlaytestReport(notes: body["notes"] as? String ?? "")
      default: break
      }
    }
  }

  @objc func closePlaytest() { NSApp.terminate(nil) }

  func driveLivePlaytest(_ event: [String: Any]) {
    guard let target = playtestLiveDestination, event["type"] as? String == "input", liveSetupStage < 4 else { return }
    let kind = event["kind"] as? String ?? ""
    if liveSetupStage == 0 && event["command"] as? Bool == true {
      liveSetupStage = 1; write("command wizlevelport")
    } else if liveSetupStage == 1 && kind == "line" {
      liveSetupStage = 2; write("line ?")
    } else if liveSetupStage == 2 && kind == "menu",
      let rows = event["items"] as? [[String: Any]],
      let row = rows.first(where: { ($0["text"] as? String ?? "").trimmingCharacters(in: .whitespaces).hasPrefix(target + ":") }),
      let id = row["id"] as? Int {
      liveSetupStage = 3; write("menu \(id)")
    } else if liveSetupStage == 3 {
      if event["command"] as? Bool == true { liveSetupStage = 4 }
      else if kind == "text" || kind == "key" { write("key 27") }
    }
  }
  @objc func showPlaytest() { if let run = playtestRun { NSWorkspace.shared.open(run) } }
  @objc func reportPlaytest() {
    guard reportDestination == nil else { return }
    let alert = NSAlert()
    alert.messageText = "Report a play-test problem"
    alert.informativeText = "Describe what looks wrong and what you tried. Atlas will capture the screen, save a copy of this disposable game, then resume it. Nothing is uploaded. Saving cancels any open game prompt."
    let notes = NSTextField(frame: NSRect(x: 0, y: 0, width: 460, height: 75))
    notes.placeholderString = "What happened? What did you expect?"
    alert.accessoryView = notes
    alert.addButton(withTitle: "Capture Report"); alert.addButton(withTitle: "Cancel")
    alert.beginSheetModal(for: window) { result in
      if result == .alertFirstButtonReturn { self.capturePlaytestReport(notes: notes.stringValue) }
    }
  }

  func capturePlaytestReport(notes: String) {
    guard let run = playtestRun, reportDestination == nil, !closing else { return }
    let destination = run.appendingPathComponent("reports/" + UUID().uuidString)
    do { try fm.createDirectory(at: destination, withIntermediateDirectories: true) }
    catch { showError("Report could not be created", error.localizedDescription); return }
    reportDestination = destination
    reportShouldResume = engine != nil
    web.evaluateJavaScript("JSON.stringify({tileset:document.getElementById('tileset-select').value,preferences:localStorage.getItem('atlasPreferences')})") { value, _ in
      try? (value as? String ?? "{}").write(to: destination.appendingPathComponent("display.json"), atomically: true, encoding: .utf8)
      self.web.takeSnapshot(with: nil) { image, error in
        guard let image, let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff), let png = rep.representation(using: .png, properties: [:]) else {
          self.reportDestination = nil
          self.showError("Screenshot failed", error?.localizedDescription ?? "The display was unavailable. Your game is still running.")
          return
        }
        do {
          try png.write(to: destination.appendingPathComponent("screen.png"))
          try notes.write(to: destination.appendingPathComponent("notes.txt"), atomically: true, encoding: .utf8)
          let metadata = run.appendingPathComponent("metadata.json")
          try self.fm.copyItem(at: metadata, to: destination.appendingPathComponent("metadata.json"))
          try Data(self.stderrTail.utf8).write(to: destination.appendingPathComponent("stderr.txt"))
          if self.playtestLiveDestination != nil {
            // A live tutorial cannot save. Capture evidence without disturbing the session.
            try Data("NetHack disables tutorial saves. Restart using the pre-entry checkpoint in metadata.json.\n".utf8).write(to: destination.appendingPathComponent("NO-TUTORIAL-SAVE.txt"))
            let trace = run.appendingPathComponent("engine.jsonl")
            try self.fm.copyItem(at: trace, to: destination.appendingPathComponent("engine.jsonl"))
            try JSONSerialization.data(withJSONObject: ["report":destination.path,"hasSave":false]).write(to: run.appendingPathComponent("report-status.json"), options: .atomic)
            self.reportDestination = nil
            self.send(["type":"message","text":"Tutorial screenshot and trace saved: \(destination.path)"])
          } else if self.engine != nil { self.write("save") } else { self.finishPlaytestReport() }
        } catch {
          self.reportDestination = nil
          self.showError("Report could not be saved", error.localizedDescription)
        }
      }
    }
  }

  func finishPlaytestReport() {
    guard let destination = reportDestination, let run = playtestRun else { return }
    reportDestination = nil
    do {
      // The engine has exited. Never copy its live save/checkpoint files.
      try fm.copyItem(at: dataDirectory, to: destination.appendingPathComponent("game"))
      let trace = run.appendingPathComponent("engine.jsonl")
      if fm.fileExists(atPath: trace.path) { try fm.copyItem(at: trace, to: destination.appendingPathComponent("engine.jsonl")) }
      let status: [String: Any] = ["report": destination.path, "hasSave": hasSave, "date": ISO8601DateFormatter().string(from: Date())]
      try JSONSerialization.data(withJSONObject: status).write(to: run.appendingPathComponent("report-status.json"), options: .atomic)
      if reportShouldResume && hasSave { launch(["mode": "standard"], restoring: true) }
      send(["type": "message", "text": "Local report saved: \(destination.path)"])
    } catch { showError("Report is incomplete", error.localizedDescription) }
  }
}
