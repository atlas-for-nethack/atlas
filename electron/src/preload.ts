// The interface sends through window.atlasHost (docs/protocol.md). Events come
// back through window.receiveNative, which the main process calls directly.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("atlasHost", {
  postMessage: (action: unknown) => ipcRenderer.send("atlas", action),
});
