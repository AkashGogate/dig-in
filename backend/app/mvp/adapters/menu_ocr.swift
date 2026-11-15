// Local macOS OCR bridge. No network, model prompts, identity or retained files.
import AppKit
import PDFKit
import Vision

func recognize(_ image: CGImage) throws -> [String] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    try VNImageRequestHandler(cgImage: image).perform([request])
    return (request.results ?? []).sorted {
        if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.015 {
            return $0.boundingBox.midY > $1.boundingBox.midY
        }
        return $0.boundingBox.minX < $1.boundingBox.minX
    }.compactMap { $0.topCandidates(1).first?.string }
}
func cgImage(_ image: NSImage) throws -> CGImage {
    guard let result = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "MenuOCR", code: 1)
    }
    guard result.width * result.height <= 40_000_000 else {
        throw NSError(domain: "MenuOCR", code: 2)
    }
    return result
}
do {
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    var pages: [[String]] = []
    if CommandLine.arguments[2] == "application/pdf" {
        guard let pdf = PDFDocument(url: url), !pdf.isLocked, pdf.pageCount > 0, pdf.pageCount <= 10 else {
            throw NSError(domain: "MenuOCR", code: 3)
        }
        for n in 0..<pdf.pageCount {
            guard let page = pdf.page(at: n) else { continue }
            // Rasterization also handles scanned PDFs; page order is preserved.
            let image = page.thumbnail(of: NSSize(width: 1800, height: 2400), for: .mediaBox)
            pages.append(try recognize(cgImage(image)))
        }
    } else {
        guard let image = NSImage(contentsOf: url) else { throw NSError(domain: "MenuOCR", code: 4) }
        pages.append(try recognize(cgImage(image)))
    }
    let data = try JSONSerialization.data(withJSONObject: ["pages": pages])
    FileHandle.standardOutput.write(data)
} catch {
    FileHandle.standardError.write(Data("Cannot read this document (PDF must be unlocked and at most 10 pages).".utf8))
    exit(1)
}
