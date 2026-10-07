import Darwin
import Foundation

/// Recovery is conservative: a checkpoint owned by a live (or inaccessible)
/// process is never touched. The upstream utility runs on copies because it
/// deletes level files as it rebuilds a save, including on some failure paths.
enum Recovery {
  enum Disposition: String { case recovered, active, skipped, failed }
  struct Report {
    let checkpoint: String
    let disposition: Disposition
    let detail: String
  }

  static func recoverInterruptedGames(in directory: URL, using executable: URL) -> [Report] {
    let fm = FileManager.default
    let prefix = String(getuid())
    let files = (try? fm.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
    return files.filter { $0.pathExtension == "0" && $0.lastPathComponent.hasPrefix(prefix) }
      .sorted { $0.lastPathComponent < $1.lastPathComponent }
      .map { checkpoint in
        let stem = checkpoint.deletingPathExtension().lastPathComponent
        func report(_ disposition: Disposition, _ detail: String) -> Report {
          Report(checkpoint: stem, disposition: disposition, detail: detail)
        }
        do {
          guard isOwnedRegularFile(checkpoint),
            let handle = try? FileHandle(forReadingFrom: checkpoint)
          else {
            return report(.skipped, "Checkpoint is not a regular file owned by this user.")
          }
          let header = try handle.read(upToCount: 1024) ?? Data()
          try handle.close()
          guard header.count >= MemoryLayout<Int32>.size else {
            return report(.skipped, "Checkpoint has no complete process identifier.")
          }
          var pid: Int32 = 0
          _ = withUnsafeMutableBytes(of: &pid) { header.prefix(4).copyBytes(to: $0) }
          guard pid > 1 else {
            return report(.skipped, "Checkpoint process identifier is invalid.")
          }
          guard knownDead(pid) else {
            return report(.active, "Another process still owns this adventure.")
          }
          // Startup-only lock files have a PID but no recovery data.
          guard header.count > 8, let end = header[8...].firstIndex(of: 0),
            let savePath = String(data: header[8..<end], encoding: .utf8),
            savePath.hasPrefix("save/"),
            [stem, stem + ".Z", stem + ".gz"].contains(String(savePath.dropFirst(5)))
          else {
            return report(.skipped, "This interrupted session has no complete checkpoint.")
          }
          let existing = try fm.contentsOfDirectory(
            atPath: directory.appendingPathComponent("save").path)
          guard !existing.contains(where: { [stem, stem + ".Z", stem + ".gz"].contains($0) }) else {
            return report(.skipped, "A saved adventure already exists; it was preserved.")
          }
          let candidates = files.filter { file in
            let name = file.lastPathComponent
            guard name.hasPrefix(stem + ".") else { return false }
            let level = name.dropFirst(stem.count + 1)
            return !level.isEmpty && level.allSatisfy(\.isNumber) && isOwnedRegularFile(file)
          }
          let staging = directory.appendingPathComponent(
            ".recovery-" + UUID().uuidString, isDirectory: true)
          try fm.createDirectory(
            at: staging, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
          defer { try? fm.removeItem(at: staging) }
          try fm.createDirectory(
            at: staging.appendingPathComponent("save"), withIntermediateDirectories: false)
          for file in candidates {
            try fm.copyItem(at: file, to: staging.appendingPathComponent(file.lastPathComponent))
          }
          // Recheck ownership after copying; PID reuse is treated as active.
          guard knownDead(pid) else {
            return report(.active, "The checkpoint owner is now active; recovery was cancelled.")
          }
          let originalHeader = try Data(contentsOf: checkpoint).prefix(header.count)
          guard originalHeader == header else {
            return report(.skipped, "The checkpoint changed during recovery preparation.")
          }
          let child = Process()
          child.executableURL = executable
          child.arguments = [stem]
          child.currentDirectoryURL = staging
          var environment = ProcessInfo.processInfo.environment
          environment["NETHACKDIR"] = staging.path
          environment["HACKDIR"] = staging.path
          environment["HOME"] = staging.path
          child.environment = environment
          child.standardInput = FileHandle.nullDevice
          let output = Pipe()
          child.standardOutput = output
          child.standardError = output
          try child.run()
          let deadline = Date().addingTimeInterval(5)
          while child.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.01) }
          if child.isRunning {
            // This is only our recovery helper operating on copies.
            kill(child.processIdentifier, SIGKILL)
            child.waitUntilExit()
            return report(.failed, "Recovery timed out. Original checkpoint files were preserved.")
          }
          child.waitUntilExit()
          let diagnostic = String(
            decoding: output.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self
          )
          .trimmingCharacters(in: .whitespacesAndNewlines)
          let recovered = staging.appendingPathComponent(savePath)
          guard child.terminationStatus == 0, isOwnedRegularFile(recovered),
            (try recovered.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) > 0
          else {
            return report(
              .failed,
              diagnostic.isEmpty
                ? "Recovery failed. Original checkpoint files were preserved." : diagnostic)
          }
          guard knownDead(pid), (try Data(contentsOf: checkpoint).prefix(header.count)) == header
          else {
            return report(.skipped, "The original session changed; its checkpoint was preserved.")
          }
          let destination = directory.appendingPathComponent(savePath)
          guard !fm.fileExists(atPath: destination.path) else {
            return report(.skipped, "A save appeared during recovery; it was preserved.")
          }
          try fm.moveItem(at: recovered, to: destination)
          let backup = directory.appendingPathComponent("Recovered Checkpoints", isDirectory: true)
            .appendingPathComponent(stem + "-" + UUID().uuidString, isDirectory: true)
          try fm.createDirectory(
            at: backup, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
          for file in candidates {
            try fm.moveItem(at: file, to: backup.appendingPathComponent(file.lastPathComponent))
          }
          return report(
            .recovered,
            "Recovered the interrupted adventure. Original checkpoints were retained in Recovered Checkpoints."
          )
        } catch {
          return report(.failed, "Recovery could not finish: " + error.localizedDescription)
        }
      }
  }

  private static func knownDead(_ pid: Int32) -> Bool {
    errno = 0
    return kill(pid, 0) == -1 && errno == ESRCH
  }

  private static func isOwnedRegularFile(_ url: URL) -> Bool {
    var metadata = stat()
    guard lstat(url.path, &metadata) == 0 else { return false }
    return metadata.st_uid == getuid() && (metadata.st_mode & S_IFMT) == S_IFREG
  }
}
