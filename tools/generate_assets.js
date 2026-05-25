const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");

const outDir = path.join(__dirname, "..", "static", "assets");
const WIDTH = 800;
const HEIGHT = 520;

const crcTable = new Uint32Array(256);
for (let n = 0; n < 256; n += 1) {
  let c = n;
  for (let k = 0; k < 8; k += 1) {
    c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  }
  crcTable[n] = c >>> 0;
}

class Raster {
  constructor(width, height, color) {
    this.width = width;
    this.height = height;
    this.data = Buffer.alloc(width * height * 4);
    this.fill(color);
  }

  fill(color) {
    for (let y = 0; y < this.height; y += 1) {
      for (let x = 0; x < this.width; x += 1) {
        this.pixel(x, y, color);
      }
    }
  }

  pixel(x, y, color) {
    const px = Math.round(x);
    const py = Math.round(y);
    if (px < 0 || px >= this.width || py < 0 || py >= this.height) return;
    const offset = (py * this.width + px) * 4;
    const alpha = color[3] / 255;
    const inv = 1 - alpha;
    this.data[offset] = Math.round(color[0] * alpha + this.data[offset] * inv);
    this.data[offset + 1] = Math.round(color[1] * alpha + this.data[offset + 1] * inv);
    this.data[offset + 2] = Math.round(color[2] * alpha + this.data[offset + 2] * inv);
    this.data[offset + 3] = 255;
  }

  rect(x, y, width, height, color) {
    const x0 = Math.max(0, Math.floor(x));
    const y0 = Math.max(0, Math.floor(y));
    const x1 = Math.min(this.width, Math.ceil(x + width));
    const y1 = Math.min(this.height, Math.ceil(y + height));
    for (let py = y0; py < y1; py += 1) {
      for (let px = x0; px < x1; px += 1) this.pixel(px, py, color);
    }
  }

  ellipse(cx, cy, rx, ry, color) {
    const x0 = Math.max(0, Math.floor(cx - rx));
    const y0 = Math.max(0, Math.floor(cy - ry));
    const x1 = Math.min(this.width, Math.ceil(cx + rx));
    const y1 = Math.min(this.height, Math.ceil(cy + ry));
    for (let y = y0; y < y1; y += 1) {
      for (let x = x0; x < x1; x += 1) {
        const dx = (x - cx) / rx;
        const dy = (y - cy) / ry;
        if (dx * dx + dy * dy <= 1) this.pixel(x, y, color);
      }
    }
  }

  circle(cx, cy, radius, color) {
    this.ellipse(cx, cy, radius, radius, color);
  }

  roundedRect(x, y, width, height, radius, color) {
    this.rect(x + radius, y, width - radius * 2, height, color);
    this.rect(x, y + radius, width, height - radius * 2, color);
    this.circle(x + radius, y + radius, radius, color);
    this.circle(x + width - radius, y + radius, radius, color);
    this.circle(x + radius, y + height - radius, radius, color);
    this.circle(x + width - radius, y + height - radius, radius, color);
  }

  polygon(points, color) {
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    const x0 = Math.max(0, Math.floor(Math.min(...xs)));
    const y0 = Math.max(0, Math.floor(Math.min(...ys)));
    const x1 = Math.min(this.width, Math.ceil(Math.max(...xs)));
    const y1 = Math.min(this.height, Math.ceil(Math.max(...ys)));
    for (let y = y0; y <= y1; y += 1) {
      for (let x = x0; x <= x1; x += 1) {
        if (insidePolygon(x, y, points)) this.pixel(x, y, color);
      }
    }
  }

  line(x1, y1, x2, y2, thickness, color) {
    const steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
    for (let index = 0; index <= steps; index += 1) {
      const t = index / steps;
      this.circle(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, thickness / 2, color);
    }
  }
}

function insidePolygon(x, y, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i, i += 1) {
    const xi = points[i][0];
    const yi = points[i][1];
    const xj = points[j][0];
    const yj = points[j][1];
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function color(hex, alpha = 255) {
  const clean = hex.replace("#", "");
  return [
    parseInt(clean.slice(0, 2), 16),
    parseInt(clean.slice(2, 4), 16),
    parseInt(clean.slice(4, 6), 16),
    alpha,
  ];
}

function writePng(fileName, raster) {
  const raw = Buffer.alloc((raster.width * 4 + 1) * raster.height);
  for (let y = 0; y < raster.height; y += 1) {
    const rawOffset = y * (raster.width * 4 + 1);
    raw[rawOffset] = 0;
    raster.data.copy(raw, rawOffset + 1, y * raster.width * 4, (y + 1) * raster.width * 4);
  }

  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(raster.width, 0);
  ihdr.writeUInt32BE(raster.height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const png = Buffer.concat([
    signature,
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
  fs.writeFileSync(path.join(outDir, fileName), png);
}

function chunk(type, data) {
  const typeBuffer = Buffer.from(type);
  const lengthBuffer = Buffer.alloc(4);
  lengthBuffer.writeUInt32BE(data.length, 0);
  const crcBuffer = Buffer.alloc(4);
  crcBuffer.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0);
  return Buffer.concat([lengthBuffer, typeBuffer, data, crcBuffer]);
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function addTable(raster, fill = "#fff6e3") {
  raster.rect(0, 330, WIDTH, 190, color(fill));
  raster.ellipse(400, 392, 260, 44, color("#6b4a2f", 32));
}

function lavash() {
  const r = new Raster(WIDTH, HEIGHT, color("#ffe9cf"));
  addTable(r, "#fff8e9");
  r.polygon([[120, 178], [618, 118], [686, 316], [190, 374]], color("#d99b58", 255));
  r.polygon([[148, 194], [594, 142], [650, 300], [205, 350]], color("#f0c073", 255));
  r.polygon([[246, 178], [544, 150], [630, 288], [300, 320]], color("#fff5dd", 255));
  r.line(240, 198, 580, 160, 18, color("#e14a34", 230));
  r.line(270, 230, 625, 270, 20, color("#60a761", 230));
  r.line(225, 260, 572, 310, 14, color("#f4b12f", 230));
  for (const [x, y] of [[335, 214], [430, 196], [515, 222], [382, 270], [492, 286]]) {
    r.circle(x, y, 24, color("#773b24"));
    r.circle(x - 6, y - 6, 9, color("#a85a32"));
  }
  r.line(176, 205, 656, 318, 5, color("#9c6234", 160));
  r.line(146, 190, 208, 356, 5, color("#9c6234", 130));
  return r;
}

function burger() {
  const r = new Raster(WIDTH, HEIGHT, color("#dff1f5"));
  addTable(r, "#fff2d4");
  r.ellipse(404, 248, 235, 96, color("#d18a2f"));
  r.ellipse(404, 230, 210, 78, color("#f1b655"));
  for (const [x, y] of [[300, 208], [372, 188], [442, 202], [506, 220]]) {
    r.ellipse(x, y, 10, 4, color("#fff6d7"));
  }
  r.rect(202, 276, 400, 34, color("#f9cf3d"));
  r.polygon([[210, 310], [610, 310], [575, 348], [230, 340]], color("#74aa52"));
  r.roundedRect(184, 330, 432, 62, 24, color("#5b2d1b"));
  r.rect(204, 392, 390, 34, color("#f9cf3d"));
  r.ellipse(400, 420, 232, 58, color("#c6762b"));
  r.ellipse(400, 398, 210, 38, color("#f2ad51"));
  return r;
}

function pizza() {
  const r = new Raster(WIDTH, HEIGHT, color("#f7e8bf"));
  addTable(r, "#fff9e4");
  r.circle(400, 270, 190, color("#c97628"));
  r.circle(400, 270, 168, color("#ffd85d"));
  r.circle(400, 270, 148, color("#ffbd45"));
  r.line(400, 270, 400, 104, 5, color("#b86624", 140));
  r.line(400, 270, 540, 356, 5, color("#b86624", 140));
  r.line(400, 270, 254, 360, 5, color("#b86624", 140));
  for (const [x, y] of [[322, 210], [444, 190], [500, 274], [386, 320], [292, 306], [455, 372]]) {
    r.circle(x, y, 27, color("#c83c33"));
    r.circle(x - 6, y - 7, 10, color("#e45b4d"));
  }
  for (const [x, y] of [[360, 242], [488, 238], [336, 352], [436, 296]]) {
    r.circle(x, y, 14, color("#5f8f3d"));
  }
  return r;
}

function combo() {
  const r = new Raster(WIDTH, HEIGHT, color("#e8f3ea"));
  addTable(r, "#fff3dc");
  r.roundedRect(92, 240, 170, 220, 18, color("#d72e28"));
  r.polygon([[92, 240], [262, 240], [230, 300], [120, 300]], color("#f84634"));
  for (const x of [126, 158, 190, 222]) {
    r.roundedRect(x, 116, 24, 170, 8, color("#ffd15c"));
  }
  r.ellipse(430, 280, 160, 62, color("#f1b655"));
  r.rect(286, 310, 288, 34, color("#f9cf3d"));
  r.roundedRect(276, 342, 305, 54, 22, color("#6a3724"));
  r.ellipse(430, 402, 166, 42, color("#d38735"));
  r.polygon([[604, 182], [716, 182], [698, 432], [622, 432]], color("#2f6f96"));
  r.polygon([[618, 204], [702, 204], [686, 410], [634, 410]], color("#bce7f0"));
  r.line(642, 118, 670, 214, 10, color("#e33424"));
  r.circle(662, 330, 22, color("#e33424", 210));
  return r;
}

function drink() {
  const r = new Raster(WIDTH, HEIGHT, color("#e9f5fb"));
  addTable(r, "#fff7e4");
  r.line(372, 82, 424, 212, 14, color("#e33424"));
  r.polygon([[252, 150], [548, 150], [506, 448], [294, 448]], color("#2f6f96"));
  r.polygon([[282, 186], [518, 186], [486, 412], [314, 412]], color("#dbf4fb"));
  r.ellipse(400, 188, 120, 28, color("#ffffff", 210));
  r.rect(304, 270, 190, 78, color("#cf315c", 215));
  for (const [x, y] of [[350, 238], [426, 258], [454, 334], [362, 360]]) {
    r.circle(x, y, 24, color("#ffffff", 130));
  }
  r.circle(394, 310, 48, color("#e33424", 230));
  r.circle(410, 294, 16, color("#ffbd35", 230));
  return r;
}

function dessert() {
  const r = new Raster(WIDTH, HEIGHT, color("#fff0f2"));
  addTable(r, "#fff9e9");
  r.polygon([[222, 270], [540, 170], [614, 330], [292, 430]], color("#5b2b24"));
  r.polygon([[248, 256], [524, 170], [580, 284], [300, 370]], color("#9a4c35"));
  r.polygon([[300, 370], [580, 284], [614, 330], [292, 430]], color("#421f1a"));
  r.line(282, 266, 542, 184, 30, color("#fff2d6"));
  r.line(304, 334, 586, 250, 20, color("#e9b24d"));
  r.circle(532, 172, 30, color("#e33424"));
  r.circle(520, 164, 9, color("#ff8a7d"));
  for (const [x, y] of [[350, 310], [438, 286], [496, 336]]) {
    r.circle(x, y, 14, color("#2f6f96", 230));
  }
  return r;
}

fs.mkdirSync(outDir, { recursive: true });
writePng("lavash.png", lavash());
writePng("burger.png", burger());
writePng("pizza.png", pizza());
writePng("combo.png", combo());
writePng("drink.png", drink());
writePng("dessert.png", dessert());
console.log(`Generated Maxway assets in ${outDir}`);
