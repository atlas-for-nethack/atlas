import Cocoa

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let dir = root.appendingPathComponent(".build/AppIcon.iconset")
try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
for size in [16, 32, 128, 256, 512] {
  for scale in [1, 2] {
    let n = size * scale
    let image = NSImage(size: NSSize(width: n, height: n))
    image.lockFocus()
    let s = CGFloat(n) / 1024
    let transform = NSAffineTransform()
    transform.scale(by: s)
    transform.concat()
    let rect = NSRect(x: 12, y: 12, width: 1000, height: 1000)
    let bg = NSBezierPath(roundedRect: rect, xRadius: 205, yRadius: 205)
    NSGradient(
      starting: NSColor(calibratedRed: 0.09, green: 0.16, blue: 0.18, alpha: 1),
      ending: NSColor(calibratedRed: 0.025, green: 0.05, blue: 0.065, alpha: 1))!.draw(
        in: bg, angle: -70)
    let gold = NSColor(calibratedRed: 0.78, green: 0.61, blue: 0.36, alpha: 1)
    gold.setStroke()
    let outer = NSBezierPath()
    outer.move(to: NSPoint(x: 242, y: 242))
    outer.line(to: NSPoint(x: 242, y: 640))
    outer.curve(
      to: NSPoint(x: 782, y: 640), controlPoint1: NSPoint(x: 242, y: 1000),
      controlPoint2: NSPoint(x: 782, y: 1000))
    outer.line(to: NSPoint(x: 782, y: 242))
    outer.lineWidth = 34
    outer.stroke()
    let inner = NSBezierPath()
    inner.move(to: NSPoint(x: 315, y: 242))
    inner.line(to: NSPoint(x: 315, y: 625))
    inner.curve(
      to: NSPoint(x: 709, y: 625), controlPoint1: NSPoint(x: 315, y: 895),
      controlPoint2: NSPoint(x: 709, y: 895))
    inner.line(to: NSPoint(x: 709, y: 242))
    inner.lineWidth = 12
    inner.stroke()
    let steps = NSBezierPath()
    for i in 0..<3 {
      let inset = CGFloat(i) * 48
      steps.move(to: NSPoint(x: 280 + inset, y: 170 + CGFloat(i) * 72))
      steps.line(to: NSPoint(x: 744 - inset, y: 170 + CGFloat(i) * 72))
    }
    steps.lineWidth = 24
    steps.stroke()
    let star = NSBezierPath()
    star.move(to: NSPoint(x: 512, y: 716))
    star.line(to: NSPoint(x: 539, y: 613))
    star.line(to: NSPoint(x: 622, y: 584))
    star.line(to: NSPoint(x: 539, y: 555))
    star.line(to: NSPoint(x: 512, y: 452))
    star.line(to: NSPoint(x: 485, y: 555))
    star.line(to: NSPoint(x: 402, y: 584))
    star.line(to: NSPoint(x: 485, y: 613))
    star.close()
    NSColor(calibratedRed: 0.92, green: 0.80, blue: 0.54, alpha: 1).setFill()
    star.fill()
    image.unlockFocus()
    let data = NSBitmapImageRep(data: image.tiffRepresentation!)!.representation(
      using: .png, properties: [:])!
    let filename = "icon_\(size)x\(size)" + (scale == 2 ? "@2x" : "") + ".png"
    try data.write(to: dir.appendingPathComponent(filename))
  }
}
