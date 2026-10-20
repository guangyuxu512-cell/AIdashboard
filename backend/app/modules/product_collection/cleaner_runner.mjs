import fs from "node:fs";
import { pathToFileURL } from "node:url";

const modulePath = process.argv[2];
if (!modulePath) process.exit(2);

try {
  const raw = fs.readFileSync(0, "utf8");
  const input = JSON.parse(raw);
  const converter = await import(pathToFileURL(modulePath).href);
  if (typeof converter.convertCompletePackage !== "function") process.exit(3);
  const result = converter.convertCompletePackage({ input, pretty: false });
  process.stdout.write(JSON.stringify(result));
} catch {
  // Raw packages and converter exception text are deliberately not echoed.
  process.exit(4);
}
