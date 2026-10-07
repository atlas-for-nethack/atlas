import Foundation
import CoreFoundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import Darwin

// Resource limits apply equally to fresh imports and persisted custom sheets.
// These bound individual buffers, not the combined peak of ImageIO and WebKit.
struct TilesetImportPolicy {
  var sourceBytes = 128 * 1024 * 1024
  var axis = 65_536
  var pixels = 64_000_000
  var rasterBytes = 256 * 1024 * 1024
  var pngBytes = 64 * 1024 * 1024
  var manifestBytes = 96 * 1024 * 1024
  var minimumTiles = 2304
}

enum TilesetImportError: LocalizedError {
  case invalid(String)
  var errorDescription: String? {
    switch self { case .invalid(let message): return message }
  }
}

struct ImportedTileset {
  let manifest: [String: Any]
  let serialized: Data
}

enum TilesetImport {
  static let pngPrefix = "data:image/png;base64,"

  static func product(_ lhs: Int, _ rhs: Int) throws -> Int {
    let (value, overflow) = lhs.multipliedReportingOverflow(by: rhs)
    guard lhs >= 0, rhs >= 0, !overflow else {
      throw TilesetImportError.invalid("The image dimensions exceed the supported range.")
    }
    return value
  }

  // JSON booleans bridge as NSNumber too. Never accept them as dimensions.
  static func integer(_ value: Any?) throws -> Int {
    guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else {
      throw TilesetImportError.invalid("Tile dimensions must be whole numbers.")
    }
    let numeric = number.doubleValue
    guard numeric.isFinite, numeric.rounded(.towardZero) == numeric,
      numeric >= 0, numeric < Double(Int.max)
    else { throw TilesetImportError.invalid("Tile dimensions must be finite whole numbers.") }
    return Int(numeric)
  }

  // Read the opened file, not a path checked before a second open. The size
  // check is advisory; the loop independently stops at limit + 1 if it grows.
  static func boundedRead(_ url: URL, limit: Int) throws -> Data {
    guard limit >= 0, limit < Int.max else {
      throw TilesetImportError.invalid("Invalid file-size limit.")
    }
    let descriptor = open(url.path, O_RDONLY | O_CLOEXEC | O_NONBLOCK)
    guard descriptor >= 0 else { throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
    let handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
    defer { try? handle.close() }
    var info = stat()
    guard fstat(descriptor, &info) == 0 else { throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
    guard info.st_mode & S_IFMT == S_IFREG else {
      throw TilesetImportError.invalid("Choose a regular PNG or BMP image file.")
    }
    guard info.st_size >= 0, info.st_size <= limit else {
      throw TilesetImportError.invalid("The custom tileset file exceeds its size limit.")
    }
    var data = Data()
    while data.count <= limit {
      let chunk = try handle.read(upToCount: min(1024 * 1024, limit + 1 - data.count)) ?? Data()
      if chunk.isEmpty { return data }
      data.append(chunk)
    }
    throw TilesetImportError.invalid("The custom tileset file exceeds its size limit.")
  }

  static func geometry(width: Int, height: Int, tileWidth: Int, tileHeight: Int,
                       depth: Int, policy: TilesetImportPolicy) throws -> (columns: Int, count: Int) {
    guard (8...256).contains(tileWidth), (8...256).contains(tileHeight),
      width > 0, height > 0, width <= policy.axis, height <= policy.axis,
      width % tileWidth == 0, height % tileHeight == 0
    else { throw TilesetImportError.invalid("The sheet dimensions do not match the tile size or exceed the image limits.") }
    guard (1...16).contains(depth) else {
      throw TilesetImportError.invalid("Only integer PNG/BMP images with up to 16 bits per component are supported.")
    }
    let pixels = try product(width, height)
    let bytesPerPixel = try product(4, (depth + 7) / 8)
    let raster = try product(pixels, bytesPerPixel)
    let columns = width / tileWidth
    let count = try product(columns, height / tileHeight)
    guard pixels <= policy.pixels, raster <= policy.rasterBytes else {
      throw TilesetImportError.invalid("The custom tileset exceeds the pixel or decoded-image memory limit.")
    }
    guard count >= policy.minimumTiles else {
      throw TilesetImportError.invalid("Choose a complete NetHack 5.0 sheet with at least \(policy.minimumTiles) tiles.")
    }
    return (columns, count)
  }

  static func decode(_ data: Data, tileWidth: Int, tileHeight: Int,
                     pngOnly: Bool, policy: TilesetImportPolicy) throws -> CGImage {
    let options = [kCGImageSourceShouldCache: false, kCGImageSourceShouldAllowFloat: false] as CFDictionary
    guard let source = CGImageSourceCreateWithData(data as CFData, options),
      let type = CGImageSourceGetType(source) as String?,
      type == UTType.png.identifier || (!pngOnly && type == UTType.bmp.identifier),
      CGImageSourceGetCount(source) == 1,
      let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, options) as? [String: Any]
    else { throw TilesetImportError.invalid("Choose a valid, single-image PNG or BMP tilesheet.") }
    let width = try integer(properties[kCGImagePropertyPixelWidth as String])
    let height = try integer(properties[kCGImagePropertyPixelHeight as String])
    let depth = try integer(properties[kCGImagePropertyDepth as String])
    _ = try geometry(width: width, height: height, tileWidth: tileWidth, tileHeight: tileHeight,
                     depth: depth, policy: policy)
    // No raster is requested until type, count, dimensions and depth pass.
    guard let image = CGImageSourceCreateImageAtIndex(source, 0, options),
      image.width == width, image.height == height,
      image.bitsPerComponent > 0, image.bitsPerComponent <= 16,
      !image.bitmapInfo.contains(.floatComponents)
    else { throw TilesetImportError.invalid("The custom tileset could not be decoded safely.") }
    _ = try geometry(width: image.width, height: image.height, tileWidth: tileWidth, tileHeight: tileHeight,
                     depth: image.bitsPerComponent, policy: policy)
    guard try product(image.bytesPerRow, image.height) <= policy.rasterBytes else {
      throw TilesetImportError.invalid("The decoded tileset exceeds the image memory limit.")
    }
    return image
  }

  private final class PNGBuffer {
    let limit: Int
    var data = Data()
    var exceeded = false
    init(limit: Int) { self.limit = limit }
  }

  static func png(_ image: CGImage, policy: TilesetImportPolicy) throws -> Data {
    var normalized = image
    if image.bitsPerComponent > 8 {
      let rowBytes = try product(image.width, 4)
      guard try product(rowBytes, image.height) <= policy.rasterBytes,
        let space = CGColorSpace(name: CGColorSpace.sRGB),
        let context = CGContext(data: nil, width: image.width, height: image.height,
          bitsPerComponent: 8, bytesPerRow: rowBytes, space: space,
          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
      else { throw TilesetImportError.invalid("The high-bit-depth tileset could not be converted within the image limits.") }
      context.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
      guard let converted = context.makeImage() else {
        throw TilesetImportError.invalid("The high-bit-depth tileset could not be converted.")
      }
      normalized = converted
    }
    let buffer = PNGBuffer(limit: policy.pngBytes)
    var callbacks = CGDataConsumerCallbacks(putBytes: { info, bytes, count in
      guard let info else { return 0 }
      let buffer = Unmanaged<PNGBuffer>.fromOpaque(info).takeUnretainedValue()
      guard !buffer.exceeded, count <= buffer.limit - buffer.data.count else {
        buffer.exceeded = true
        return 0
      }
      buffer.data.append(bytes.assumingMemoryBound(to: UInt8.self), count: count)
      return count
    }, releaseConsumer: nil)
    guard let consumer = CGDataConsumer(info: Unmanaged.passUnretained(buffer).toOpaque(), cbks: &callbacks),
      let destination = CGImageDestinationCreateWithDataConsumer(consumer, UTType.png.identifier as CFString, 1, nil)
    else { throw TilesetImportError.invalid("The PNG encoder could not be started.") }
    let complete = withExtendedLifetime(buffer) {
      CGImageDestinationAddImage(destination, normalized, nil)
      return CGImageDestinationFinalize(destination)
    }
    guard !buffer.exceeded else { throw TilesetImportError.invalid("The converted PNG exceeds the output size limit.") }
    guard complete else { throw TilesetImportError.invalid("The image could not be converted to PNG.") }
    return buffer.data
  }

  static func manifest(png: Data, name: String, image: CGImage, tileWidth: Int, tileHeight: Int,
                       policy: TilesetImportPolicy) throws -> ImportedTileset {
    guard png.count <= policy.pngBytes else { throw TilesetImportError.invalid("The PNG exceeds the output size limit.") }
    let dimensions = try geometry(width: image.width, height: image.height, tileWidth: tileWidth,
                                  tileHeight: tileHeight, depth: image.bitsPerComponent, policy: policy)
    // Whitelist only ordinary row-major sheet fields. Never retain path/url,
    // projectedFrames, regionalMaterials or original-art rendering extensions.
    let tile: [String: Any] = ["id": "custom", "name": String(name.prefix(200)),
      "file": pngPrefix + png.base64EncodedString(), "tileWidth": tileWidth, "tileHeight": tileHeight,
      "columns": dimensions.columns, "count": dimensions.count, "version": "5.0.0"]
    let serialized = try JSONSerialization.data(withJSONObject: tile, options: [.withoutEscapingSlashes])
    guard serialized.count <= policy.manifestBytes else {
      throw TilesetImportError.invalid("The saved custom tileset exceeds the storage size limit.")
    }
    return ImportedTileset(manifest: tile, serialized: serialized)
  }

  static func convert(_ url: URL, tileWidth: Int, tileHeight: Int,
                      policy: TilesetImportPolicy = TilesetImportPolicy()) throws -> ImportedTileset {
    let data = try boundedRead(url, limit: policy.sourceBytes)
    let image = try decode(data, tileWidth: tileWidth, tileHeight: tileHeight, pngOnly: false, policy: policy)
    let encoded = try png(image, policy: policy)
    return try manifest(png: encoded, name: url.deletingPathExtension().lastPathComponent,
                        image: image, tileWidth: tileWidth, tileHeight: tileHeight, policy: policy)
  }

  static func reload(_ url: URL, policy: TilesetImportPolicy = TilesetImportPolicy()) throws -> ImportedTileset {
    let data = try boundedRead(url, limit: policy.manifestBytes)
    guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
      object["id"] as? String == "custom", object["version"] as? String == "5.0.0",
      let name = object["name"] as? String, let file = object["file"] as? String,
      file.hasPrefix(pngPrefix)
    else { throw TilesetImportError.invalid("The saved custom tileset is not a supported NetHack 5.0 PNG sheet.") }
    let width = try integer(object["tileWidth"]), height = try integer(object["tileHeight"])
    let encoded = file.dropFirst(pngPrefix.count)
    let (rounded, overflow) = policy.pngBytes.addingReportingOverflow(2)
    guard policy.pngBytes >= 0, !overflow,
      encoded.utf8.count <= (try product(rounded / 3, 4)),
      encoded.utf8.count % 4 == 0
    else { throw TilesetImportError.invalid("The saved PNG exceeds the output size limit.") }
    // Foundation strict decoding rejects whitespace and non-base64 characters.
    // Require canonical padding as well, including unused trailing bits.
    guard let png = Data(base64Encoded: String(encoded)), png.count <= policy.pngBytes,
      png.base64EncodedString() == encoded
    else { throw TilesetImportError.invalid("The saved tileset contains invalid PNG base64 data.") }
    let image = try decode(png, tileWidth: width, tileHeight: height, pngOnly: true, policy: policy)
    // Re-encoding high-bit-depth persistence normalizes it like a fresh import.
    let normalized = image.bitsPerComponent > 8 ? try self.png(image, policy: policy) : png
    return try manifest(png: normalized, name: name, image: image, tileWidth: width, tileHeight: height, policy: policy)
  }

  static func persist(_ tile: ImportedTileset, to url: URL) throws {
    try tile.serialized.write(to: url, options: .atomic)
  }
}
