import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(fileURLToPath(new URL("../frontend/dist/", import.meta.url)));
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon" };
createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://localhost");
    const path = resolve(root, "." + decodeURIComponent(url.pathname));
    if (path !== root && !path.startsWith(root + sep)) { response.writeHead(403); response.end(); return; }
    let target = path;
    try { if (!(await stat(target)).isFile()) target = resolve(root, "index.html"); }
    catch { if (extname(path)) { response.writeHead(404); response.end(); return; } target = resolve(root, "index.html"); }
    const bytes = await readFile(target);
    response.writeHead(200, { "Content-Type": types[extname(target)] || "application/octet-stream", "X-Content-Type-Options": "nosniff",
      "Cache-Control": extname(target) === ".html" ? "no-cache" : "public, max-age=3600" });
    response.end(bytes);
  } catch { response.writeHead(400); response.end("Unable to serve this request."); }
}).listen(5173, "127.0.0.1", () => console.log("Vocalis: http://127.0.0.1:5173"));
