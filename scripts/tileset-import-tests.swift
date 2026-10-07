import Foundation
import CoreGraphics
import ImageIO

@main struct TilesetImportTests {
  static func require(_ value: Bool) { precondition(value) }
  static func reject(_ label: String, _ body: () throws -> Void) {
    do { try body(); fatalError("Unexpected acceptance: \(label)") }
    catch { print("PASS reject \(label): \(error.localizedDescription)") }
  }
  static func main() throws {
    let args = CommandLine.arguments
    if args[1] == "benchmark" {
      let start = Date()
      let source = URL(fileURLWithPath: args[2]), destination = URL(fileURLWithPath: args[3])
      let width = Int(args[4])!, height = Int(args[5])!
      let tile = try TilesetImport.convert(source, tileWidth: width, tileHeight: height)
      try TilesetImport.persist(tile, to: destination)
      let restored = try TilesetImport.reload(destination)
      require(restored.manifest["count"] as? Int == tile.manifest["count"] as? Int)
      let result: [String: Any] = ["passed": true, "sourceBytes": try Data(contentsOf: source).count,
        "manifestBytes": tile.serialized.count, "seconds": Date().timeIntervalSince(start),
        "columns": tile.manifest["columns"]!, "count": tile.manifest["count"]!]
      print(String(data: try JSONSerialization.data(withJSONObject: result), encoding: .utf8)!)
      return
    }
    let root = URL(fileURLWithPath: args[1])
    var policy = TilesetImportPolicy(); policy.minimumTiles = 1
    let mini = root.appendingPathComponent("mini.png")
    let baseline = try TilesetImport.convert(mini, tileWidth: 8, tileHeight: 8, policy: policy)
    let manifest = root.appendingPathComponent("persisted.json")
    try TilesetImport.persist(baseline, to: manifest)
    let original = try Data(contentsOf: manifest)
    let pngSize = Data(base64Encoded: (baseline.manifest["file"] as! String).dropFirst(TilesetImport.pngPrefix.count).description)!.count
    var exact = policy
    exact.axis = 8; exact.pixels = 64; exact.rasterBytes = 256
    exact.sourceBytes = try Data(contentsOf: mini).count
    exact.pngBytes = pngSize; exact.manifestBytes = original.count
    _ = try TilesetImport.convert(mini, tileWidth: 8, tileHeight: 8, policy: exact)
    _ = try TilesetImport.reload(manifest, policy: exact)
    for field in ["axis", "pixels", "raster", "source", "png", "manifest"] {
      var below = exact
      switch field {
      case "axis": below.axis -= 1
      case "pixels": below.pixels -= 1
      case "raster": below.rasterBytes -= 1
      case "source": below.sourceBytes -= 1
      case "png": below.pngBytes -= 1
      default: below.manifestBytes -= 1
      }
      reject("\(field) import boundary") { _ = try TilesetImport.convert(mini, tileWidth: 8, tileHeight: 8, policy: below) }
      if field != "source" {
        reject("\(field) reload boundary") { _ = try TilesetImport.reload(manifest, policy: below) }
      }
      require(try Data(contentsOf: manifest) == original)
    }
    print("PASS all exact resource thresholds and just-over-limit rejections")
    for value: Any in [true, false, 1.5, -1, Double.infinity, Double.nan, "32", Double(Int.max)] {
      reject("nonintegral/invalid dimension \(value)") { _ = try TilesetImport.integer(value) }
    }
    require(try TilesetImport.integer(32.0) == 32)
    reject("overflow product") { _ = try TilesetImport.product(Int.max, 2) }
    reject("negative product") { _ = try TilesetImport.product(-1, 3) }
    for width in [0, -1, Int.max] {
      reject("invalid/overflow geometry \(width)") {
        _ = try TilesetImport.geometry(width: width, height: 8, tileWidth: 8, tileHeight: 8, depth: 8, policy: policy)
      }
    }
    for (name, w, h) in [("rectangular.png",15,25), ("rgba32.png",32,32), ("rgba64.png",64,64),
                         ("palette.png",16,16), ("rgb.bmp",16,16), ("palette.bmp",16,16),
                         ("rgba16.png",16,16)] {
      let tile = try TilesetImport.convert(root.appendingPathComponent(name), tileWidth: w, tileHeight: h)
      require(tile.manifest["count"] as? Int == 2304)
      try TilesetImport.persist(tile, to: manifest)
      let restored = try TilesetImport.reload(manifest)
      require(restored.manifest["tileWidth"] as? Int == w && restored.manifest["tileHeight"] as? Int == h)
      if name == "rgba32.png" {
        try tile.serialized.write(to: root.deletingLastPathComponent().appendingPathComponent("native-valid-import.json"))
      }
      print("PASS compatible import/reload \(name) \(w)x\(h)")
    }
    for name in ["oversized.png", "zero.png", "animated.png", "invalid.png", "not-png.gif"] {
      reject("metadata/type/count \(name)") {
        _ = try TilesetImport.convert(root.appendingPathComponent(name), tileWidth: 8, tileHeight: 8, policy: policy)
      }
    }
    let high = try Data(contentsOf: root.appendingPathComponent("rgba16.png"))
    var lowRaster = TilesetImportPolicy(); lowRaster.rasterBytes = 768 * 768 * 4
    reject("16-bit predecode estimate") {
      _ = try TilesetImport.decode(high, tileWidth: 16, tileHeight: 16, pngOnly: true, policy: lowRaster)
    }
    let normalized = try TilesetImport.convert(root.appendingPathComponent("rgba16.png"), tileWidth: 16, tileHeight: 16)
    let normalizedPNG = Data(base64Encoded: (normalized.manifest["file"] as! String).dropFirst(TilesetImport.pngPrefix.count).description)!
    require(try TilesetImport.decode(normalizedPNG, tileWidth: 16, tileHeight: 16, pngOnly: true, policy: TilesetImportPolicy()).bitsPerComponent == 8)
    print("PASS 16-bit compatibility with bounded 8-bit normalization")
    var persistedHigh = normalized.manifest
    persistedHigh["file"] = TilesetImport.pngPrefix + high.base64EncodedString()
    try JSONSerialization.data(withJSONObject: persistedHigh).write(to: manifest)
    let highReload = try TilesetImport.reload(manifest)
    let highReloadPNG = Data(base64Encoded: (highReload.manifest["file"] as! String).dropFirst(TilesetImport.pngPrefix.count).description)!
    require(try TilesetImport.decode(highReloadPNG, tileWidth: 16, tileHeight: 16, pngOnly: true, policy: TilesetImportPolicy()).bitsPerComponent == 8)
    print("PASS direct high-bit-depth persistence uses the same bounded normalization")

    func reloadObject(_ object: [String: Any]) throws -> ImportedTileset {
      try JSONSerialization.data(withJSONObject: object).write(to: manifest)
      return try TilesetImport.reload(manifest, policy: policy)
    }
    var hostile = baseline.manifest
    hostile["path"] = "https://example.invalid/remote.png"; hostile["url"] = "file:///tmp/other.png"
    hostile["projectedFrames"] = ["frames": [:]]; hostile["regionalMaterials"] = ["earth": [:]]
    hostile["lanternWalls"] = [:]; hostile["columns"] = -100; hostile["count"] = 999999
    let sanitized = try reloadObject(hostile)
    require(Set(sanitized.manifest.keys) == Set(baseline.manifest.keys))
    require(sanitized.manifest["columns"] as? Int == 1 && sanitized.manifest["count"] as? Int == 1)
    print("PASS persisted manifest whitelist and recomputed geometry")
    for (key, value): (String, Any) in [("tileWidth",true), ("tileHeight",8.5), ("tileWidth",-8),
                                       ("version","3.6"), ("id","lantern"), ("file","file:///tmp/a.png"),
                                       ("file",TilesetImport.pngPrefix + "AAAA\n"),
                                       ("file",TilesetImport.pngPrefix + "====")] {
      var invalid = baseline.manifest; invalid[key] = value
      reject("persisted \(key)=\(value)") { _ = try reloadObject(invalid) }
      let preserved = try Data(contentsOf: manifest)
      reject("invalid reload remains invalid") { _ = try TilesetImport.reload(manifest, policy: policy) }
      require(try Data(contentsOf: manifest) == preserved)
    }
    try Data("not JSON".utf8).write(to: manifest)
    reject("invalid JSON") { _ = try TilesetImport.reload(manifest, policy: policy) }
    try TilesetImport.persist(baseline, to: manifest)
    let protected = try Data(contentsOf: manifest)
    let directory = root.appendingPathComponent("unwritable-destination")
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
    let marker = directory.appendingPathComponent("marker")
    try Data("keep".utf8).write(to: marker)
    reject("atomic persistence failure") { try TilesetImport.persist(baseline, to: directory) }
    require(try Data(contentsOf: marker) == Data("keep".utf8))
    require(try Data(contentsOf: manifest) == protected)
    let file = root.appendingPathComponent("bounded")
    try Data([1,2,3,4]).write(to: file)
    require(try TilesetImport.boundedRead(file, limit: 4).count == 4)
    reject("bounded read exact+1") { _ = try TilesetImport.boundedRead(file, limit: 3) }
    reject("directory read") { _ = try TilesetImport.boundedRead(directory, limit: 100) }
    print("PASS failure preservation, bounded reads and atomic persistence")
  }
}
