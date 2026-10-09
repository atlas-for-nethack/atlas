// Checkpoint recovery for the Electron host, as native/Recovery.swift does it.
// A checkpoint owned by a live (or unknown) process is never touched. The
// upstream utility runs on copies in a private staging folder, because it
// deletes level files as it rebuilds a save, including on some failure paths.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export type Disposition = "recovered" | "active" | "skipped" | "failed";
export interface Report { checkpoint: string; disposition: Disposition; detail: string }

const windows = process.platform === "win32";
// Windows saves NAME.NetHack-saved-game beside the checkpoint NAME.0. Linux
// saves save/<uid>NAME, optionally compressed, beside <uid>NAME.0.
const saveNames = (stem: string) =>
  windows ? [stem + ".NetHack-saved-game"] : [stem, stem + ".Z", stem + ".gz"].map((name) => "save/" + name);

function knownDead(pid: number) {
  try {
    process.kill(pid, 0);
    return false;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "ESRCH";
  }
}

function isOwnedRegularFile(file: string) {
  try {
    const stat = fs.lstatSync(file);
    return stat.isFile() && (windows || stat.uid === process.getuid!());
  } catch {
    return false;
  }
}

function readHeader(file: string) {
  const handle = fs.openSync(file, "r");
  try {
    const header = Buffer.alloc(1024);
    return header.subarray(0, fs.readSync(handle, header, 0, header.length, 0));
  } finally {
    fs.closeSync(handle);
  }
}

export function recoverInterruptedGames(directory: string, executable: string): Report[] {
  const prefix = windows ? "" : String(process.getuid!());
  let names: string[];
  try {
    names = fs.readdirSync(directory);
  } catch {
    return [];
  }
  return names.filter((name) => name.endsWith(".0") && name.length > 2 && name.startsWith(prefix)).sort()
    .map((name) => {
      const checkpoint = path.join(directory, name);
      const stem = name.slice(0, -2);
      const report = (disposition: Disposition, detail: string): Report => ({ checkpoint: stem, disposition, detail });
      let staging: string | null = null;
      try {
        if (!isOwnedRegularFile(checkpoint)) return report("skipped", "Checkpoint is not a regular file owned by this user.");
        const header = readHeader(checkpoint);
        if (header.length < 4) return report("skipped", "Checkpoint has no complete process identifier.");
        const pid = header.readInt32LE(0);
        if (pid <= 1) return report("skipped", "Checkpoint process identifier is invalid.");
        if (!knownDead(pid)) return report("active", "Another process still owns this adventure.");
        // Startup-only lock files have a PID but no recovery data.
        const end = header.length > 8 ? header.indexOf(0, 8) : -1;
        const savePath = end > 8 ? header.subarray(8, end).toString("utf8") : "";
        if (!saveNames(stem).includes(savePath))
          return report("skipped", "This interrupted session has no complete checkpoint.");
        if (saveNames(stem).some((save) => fs.existsSync(path.join(directory, save))))
          return report("skipped", "A saved adventure already exists; it was preserved.");
        const candidates = names.filter((file) => {
          const level = file.slice(stem.length + 1);
          return file.startsWith(stem + ".") && /^\d+$/.test(level) && isOwnedRegularFile(path.join(directory, file));
        });
        staging = path.join(directory, ".recovery-" + randomUUID());
        fs.mkdirSync(staging, { mode: 0o700 });
        if (!windows) fs.mkdirSync(path.join(staging, "save"));
        for (const file of candidates) fs.copyFileSync(path.join(directory, file), path.join(staging, file));
        // Recheck ownership after copying; PID reuse is treated as active.
        if (!knownDead(pid)) return report("active", "The checkpoint owner is now active; recovery was cancelled.");
        if (!readHeader(checkpoint).equals(header))
          return report("skipped", "The checkpoint changed during recovery preparation.");
        // -d makes the utility work in the staging folder on every platform.
        const result = spawnSync(executable, ["-d", staging, stem], {
          cwd: staging, input: "", timeout: 5000, killSignal: "SIGKILL", windowsHide: true,
          env: { ...process.env, NETHACKDIR: staging, HACKDIR: staging, HOME: staging },
        });
        if (result.error && (result.error as NodeJS.ErrnoException).code === "ETIMEDOUT")
          return report("failed", "Recovery timed out. Original checkpoint files were preserved.");
        const diagnostic = Buffer.concat([result.stdout ?? Buffer.alloc(0), result.stderr ?? Buffer.alloc(0)])
          .toString().trim();
        const recovered = path.join(staging, savePath);
        if (result.status !== 0 || !isOwnedRegularFile(recovered) || fs.statSync(recovered).size === 0)
          return report("failed", diagnostic || "Recovery failed. Original checkpoint files were preserved.");
        if (!knownDead(pid) || !readHeader(checkpoint).equals(header))
          return report("skipped", "The original session changed; its checkpoint was preserved.");
        const destination = path.join(directory, savePath);
        if (fs.existsSync(destination)) return report("skipped", "A save appeared during recovery; it was preserved.");
        fs.renameSync(recovered, destination);
        const backup = path.join(directory, "Recovered Checkpoints", stem + "-" + randomUUID());
        fs.mkdirSync(backup, { recursive: true, mode: 0o700 });
        for (const file of candidates) fs.renameSync(path.join(directory, file), path.join(backup, file));
        return report("recovered",
          "Recovered the interrupted adventure. Original checkpoints were retained in Recovered Checkpoints.");
      } catch (error) {
        return report("failed", "Recovery could not finish: " + (error as Error).message);
      } finally {
        if (staging) fs.rmSync(staging, { recursive: true, force: true });
      }
    });
}
