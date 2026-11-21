// Generates optimised brand assets from the official artwork in public/brand
// (copied unchanged from the Hack UI kit). Run: node scripts/brand-assets.mjs
import sharp from "sharp";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const dir = fileURLToPath(new URL("../public/brand/", import.meta.url));
const app = fileURLToPath(new URL("../app/", import.meta.url));
mkdirSync(dir, { recursive: true });

for (const name of ["basket-logo", "cart-body", "cart-wheels"]) {
  const src = `${dir}${name}.png`;
  await sharp(src).webp({ quality: 92, alphaQuality: 100, effort: 6 }).toFile(`${dir}${name}.webp`);
  await sharp(src).avif({ quality: 70, effort: 6 }).toFile(`${dir}${name}.avif`);
}
// Header-size logo (2x of a 34px-tall mark) to avoid shipping the full-size file.
await sharp(`${dir}basket-logo.png`).resize({ height: 68 }).webp({ quality: 92, alphaQuality: 100 }).toFile(`${dir}basket-logo-68.webp`);
await sharp(`${dir}basket-logo.png`).resize({ height: 68 }).png({ compressionLevel: 9 }).toFile(`${dir}basket-logo-68.png`);

// App icon: the official yellow cart mark + wheels on black, padded (logo unchanged).
async function icon(size, file, radius) {
  const cartW = Math.round(size * 0.62);
  const body = await sharp(`${dir}cart-body.png`).resize({ width: cartW }).toBuffer();
  const wheels = await sharp(`${dir}cart-wheels.png`).resize({ width: cartW }).toBuffer();
  const bh = (await sharp(body).metadata()).height;
  const wh = (await sharp(wheels).metadata()).height;
  const top = Math.round((size - bh - wh) / 2);
  const left = Math.round((size - cartW) / 2);
  const bg = Buffer.from(`<svg width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="${radius}" fill="#080808"/></svg>`);
  await sharp(bg)
    .composite([{ input: body, top, left }, { input: wheels, top: top + bh, left }])
    .png()
    .toFile(file);
}
await icon(512, `${app}icon.png`, 112);
await icon(180, `${app}apple-icon.png`, 0);
console.log("brand assets written");
