export const PDF_CAPTURE_WIDTH_PX = 794;

export function pdfSafeFilePart(value) {
    return String(value || "документ")
        .replace(/[\\/:*?"<>|]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function waitNextFrame() {
    return new Promise((resolve) => {
        if (typeof requestAnimationFrame === "function") {
            requestAnimationFrame(() => requestAnimationFrame(resolve));
            return;
        }
        setTimeout(resolve, 16);
    });
}

function sliceCanvas(source, startY, height) {
    const start = Math.max(0, Math.round(startY));
    const sliceH = Math.max(1, Math.round(height));
    const canvas = document.createElement("canvas");
    canvas.width = source.width;
    canvas.height = sliceH;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(source, 0, start, source.width, sliceH, 0, 0, source.width, sliceH);
    return canvas;
}

/**
 * Capture a DOM node at full height and download a multi-page A4 PDF.
 * Does not use window.print().
 */
export async function saveElementAsPdf(element, { filename, hideSelectors = [] } = {}) {
    if (!element) {
        throw new Error("Нет карточки для сохранения в PDF");
    }

    const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
    ]);

    const host = document.createElement("div");
    host.className = "pdf-export-host";
    host.setAttribute("aria-hidden", "true");

    const clone = element.cloneNode(true);
    clone.classList.add("pdf-export-clone");
    clone.style.maxHeight = "none";
    clone.style.overflow = "visible";
    clone.style.height = "auto";
    clone.style.width = `${PDF_CAPTURE_WIDTH_PX}px`;
    clone.style.boxSizing = "border-box";
    clone.style.boxShadow = "none";
    clone.style.borderRadius = "0";
    clone.style.margin = "0";
    clone.style.transform = "none";

    hideSelectors.forEach((selector) => {
        clone.querySelectorAll(selector).forEach((node) => node.remove());
    });

    host.appendChild(clone);
    document.body.appendChild(host);

    try {
        if (document.fonts?.ready) {
            await document.fonts.ready.catch(() => undefined);
        }
        await waitNextFrame();

        const canvas = await html2canvas(clone, {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff",
            logging: false,
            windowWidth: PDF_CAPTURE_WIDTH_PX,
            windowHeight: Math.max(clone.scrollHeight, clone.offsetHeight, 1),
            width: PDF_CAPTURE_WIDTH_PX,
            height: Math.max(clone.scrollHeight, clone.offsetHeight, 1),
            x: 0,
            y: 0,
            scrollX: 0,
            scrollY: 0,
            foreignObjectRendering: false,
        });

        const pdf = new jsPDF({ orientation: "p", unit: "mm", format: "a4", compress: true });
        const pageW = pdf.internal.pageSize.getWidth();
        const pageH = pdf.internal.pageSize.getHeight();
        const margin = 10;
        const usableW = pageW - margin * 2;
        const usableH = pageH - margin * 2;
        const pageHeightPx = Math.floor((usableH * canvas.width) / usableW);

        let offsetY = 0;
        let pageIndex = 0;
        while (offsetY < canvas.height) {
            const remaining = canvas.height - offsetY;
            const sliceHeight = Math.min(pageHeightPx, remaining);
            const pageCanvas = sliceCanvas(canvas, offsetY, sliceHeight);
            const sliceMm = (sliceHeight * usableW) / canvas.width;
            if (pageIndex > 0) pdf.addPage();
            pdf.addImage(pageCanvas.toDataURL("image/png"), "PNG", margin, margin, usableW, sliceMm);
            offsetY += sliceHeight;
            pageIndex += 1;
            if (pageIndex > 40) break;
        }

        pdf.save(String(filename || "результат.pdf"));
        return { pages: pageIndex, filename: String(filename || "результат.pdf") };
    } finally {
        host.remove();
    }
}
