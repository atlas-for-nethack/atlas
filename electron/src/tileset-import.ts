// Custom tileset import for the Electron host, with the limits of
// native/TilesetImport.swift. Electron's image decoder reads PNG only, so BMP
// sheets, which the Mac also accepts, are refused here.
import fs from "node:fs";
import path from "node:path";
import { nativeImage, type NativeImage } from "electron";

export const policy = {
  sourceBytes: 128 * 1024 * 1024, axis: 65_536, pixels: 64_000_000, rasterBytes: 256 * 1024 * 1024,
  pngBytes: 64 * 1024 * 1024, manifestBytes: 96 * 1024 * 1024, minimumTiles: 2304,
};
const PNG_PREFIX = "data:image/png;base64,";
const SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

export type Manifest = Record<string, unknown>;
export interface ImportedTileset { manifest: Manifest; serialized: string }

const invalid = (message: string) => new Error(message);

// JSON booleans and numeric strings are never dimensions.
export function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0)
    throw invalid("Tile dimensions must be finite whole numbers.");
  return value;
}

// Read the opened file, not a path checked before a second open.
function boundedRead(file: string, limit: number): Buffer {
  const handle = fs.openSync(file, "r");
  try {
    const stat = fs.fstatSync(handle);
    if (!stat.isFile()) throw invalid("Choose a regular PNG image file.");
    if (stat.size > limit) throw invalid("The custom tileset file exceeds its size limit.");
    const data = Buffer.alloc(Math.min(stat.size, limit) + 1);
    let length = 0, read: number;
    while (length < data.length && (read = fs.readSync(handle, data, length, data.length - length, null)) > 0)
      length += read;
    if (length > limit) throw invalid("The custom tileset file exceeds its size limit.");
    return data.subarray(0, length);
  } finally {
    fs.closeSync(handle);
  }
}

function geometry(width: number, height: number, tileWidth: number, tileHeight: number, depth: number) {
  if (tileWidth < 8 || tileWidth > 256 || tileHeight < 8 || tileHeight > 256 || width <= 0 || height <= 0 ||
      width > policy.axis || height > policy.axis || width % tileWidth || height % tileHeight)
    throw invalid("The sheet dimensions do not match the tile size or exceed the image limits.");
  if (depth < 1 || depth > 16) throw invalid("Only integer PNG images with up to 16 bits per component are supported.");
  const pixels = width * height;
  if (pixels > policy.pixels || pixels * 4 * Math.ceil(depth / 8) > policy.rasterBytes)
    throw invalid("The custom tileset exceeds the pixel or decoded-image memory limit.");
  const columns = width / tileWidth, count = columns * (height / tileHeight);
  if (count < policy.minimumTiles)
    throw invalid(`Choose a complete NetHack 5.0 sheet with at least ${policy.minimumTiles} tiles.`);
  return { columns, count };
}

// Check the header and every chunk before any raster is decoded.
function pngHeader(data: Buffer) {
  const fail = () => invalid("Choose a valid, single-image PNG tilesheet.");
  if (data.length < 33 || !data.subarray(0, 8).equals(SIGNATURE) || data.toString("latin1", 12, 16) !== "IHDR")
    throw fail();
  let offset = 8;
  while (offset + 12 <= data.length) {
    const length = data.readUInt32BE(offset), kind = data.toString("latin1", offset + 4, offset + 8);
    if (kind === "acTL") throw fail();
    offset += 12 + length;
    if (kind === "IEND") break;
  }
  if (offset > data.length) throw fail();
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20), depth: data[24] };
}

function decode(data: Buffer, tileWidth: number, tileHeight: number) {
  const { width, height, depth } = pngHeader(data);
  geometry(width, height, tileWidth, tileHeight, depth);
  const image = nativeImage.createFromBuffer(data);
  const size = image.getSize();
  if (image.isEmpty() || size.width !== width || size.height !== height)
    throw invalid("The custom tileset could not be decoded safely.");
  return { image, depth };
}

function manifest(png: Buffer, name: string, image: NativeImage, tileWidth: number, tileHeight: number): ImportedTileset {
  if (png.length > policy.pngBytes) throw invalid("The converted PNG exceeds the output size limit.");
  const { width, height } = image.getSize();
  const { columns, count } = geometry(width, height, tileWidth, tileHeight, 8);
  // Whitelist only ordinary row-major sheet fields.
  const tile: Manifest = {
    id: "custom", name: Array.from(name).slice(0, 200).join(""), file: PNG_PREFIX + png.toString("base64"),
    tileWidth, tileHeight, columns, count, version: "5.0.0",
  };
  const serialized = JSON.stringify(tile);
  if (Buffer.byteLength(serialized) > policy.manifestBytes)
    throw invalid("The saved custom tileset exceeds the storage size limit.");
  return { manifest: tile, serialized };
}

export function convert(file: string, tileWidth: unknown, tileHeight: unknown): ImportedTileset {
  const width = integer(tileWidth), height = integer(tileHeight);
  const { image } = decode(boundedRead(file, policy.sourceBytes), width, height);
  return manifest(image.toPNG(), path.parse(file).name, image, width, height);
}

export function reload(file: string): ImportedTileset {
  let object: Manifest;
  try {
    object = JSON.parse(boundedRead(file, policy.manifestBytes).toString("utf8"));
  } catch (error) {
    throw (error as Error).message.startsWith("The custom") ? error : invalid("The saved custom tileset is not valid JSON.");
  }
  const encoded = typeof object?.file === "string" && object.file.startsWith(PNG_PREFIX)
    ? object.file.slice(PNG_PREFIX.length) : null;
  if (object?.id !== "custom" || object.version !== "5.0.0" || typeof object.name !== "string" || encoded === null)
    throw invalid("The saved custom tileset is not a supported NetHack 5.0 PNG sheet.");
  const width = integer(object.tileWidth), height = integer(object.tileHeight);
  if (encoded.length > Math.floor((policy.pngBytes + 2) / 3) * 4 || encoded.length % 4)
    throw invalid("The saved PNG exceeds the output size limit.");
  // Require canonical base64, including padding and unused trailing bits.
  const png = Buffer.from(encoded, "base64");
  if (png.length > policy.pngBytes || png.toString("base64") !== encoded)
    throw invalid("The saved tileset contains invalid PNG base64 data.");
  const { image, depth } = decode(png, width, height);
  // Re-encoding high-bit-depth persistence normalizes it like a fresh import.
  return manifest(depth > 8 ? image.toPNG() : png, object.name, image, width, height);
}

// Replace the saved import only after the new one is completely written.
export function persist(tile: ImportedTileset, file: string) {
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, tile.serialized, { mode: 0o600 });
  fs.renameSync(temporary, file);
}
