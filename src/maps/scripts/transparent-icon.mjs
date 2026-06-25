import sharp from 'sharp';

/**
 * Flood-fill an icon's solid background to transparency, starting from the
 * edges so only the outer background is removed (interior pixels that happen to
 * match the background colour are preserved). Returns a transparent PNG buffer
 * at the source resolution.
 *
 * @param {string} path - source PNG path
 * @param {{r:number,g:number,b:number}} [bg] - background colour to clear
 * @param {number} [threshold] - max per-channel Manhattan distance treated as bg
 * @returns {Promise<Buffer>}
 */
export async function makeTransparentIconBuffer(path, bg = { r: 13, g: 27, b: 42 }, threshold = 44) {
    const { data, info } = await sharp(path).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const { width, height } = info;
    const visited = new Uint8Array(width * height);
    const queue = new Int32Array(width * height);
    let head = 0;
    let tail = 0;

    const isBackground = (pixel) => {
        const offset = pixel * 4;
        const distance =
            Math.abs(data[offset] - bg.r) +
            Math.abs(data[offset + 1] - bg.g) +
            Math.abs(data[offset + 2] - bg.b);
        return distance <= threshold;
    };

    const enqueue = (pixel) => {
        if (visited[pixel] || !isBackground(pixel)) return;
        visited[pixel] = 1;
        queue[tail++] = pixel;
    };

    for (let x = 0; x < width; x += 1) {
        enqueue(x);
        enqueue((height - 1) * width + x);
    }
    for (let y = 0; y < height; y += 1) {
        enqueue(y * width);
        enqueue(y * width + width - 1);
    }

    while (head < tail) {
        const pixel = queue[head++];
        const x = pixel % width;
        const y = Math.floor(pixel / width);

        data[pixel * 4 + 3] = 0;

        if (x > 0) enqueue(pixel - 1);
        if (x < width - 1) enqueue(pixel + 1);
        if (y > 0) enqueue(pixel - width);
        if (y < height - 1) enqueue(pixel + width);
    }

    return sharp(data, { raw: { width, height, channels: 4 } }).png().toBuffer();
}

/** Same as {@link makeTransparentIconBuffer} but returns a data URL. */
export async function makeTransparentIconDataUrl(path, bg, threshold) {
    const png = await makeTransparentIconBuffer(path, bg, threshold);
    return `data:image/png;base64,${png.toString('base64')}`;
}
