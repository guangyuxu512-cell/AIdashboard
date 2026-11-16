// Reuse the actual Vite config, but do not load ignored workstation .env files.
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { root } from "./contracts.mjs";

const project = process.argv[2];
if (
  !["frontend", "mobile"].includes(project) ||
  !process.env.VERIFY_EMPTY_ENV_DIR
)
  throw new Error("Use root verify with its isolated environment");
const directory = path.join(root, project);
const require = createRequire(path.join(directory, "package.json"));
const { build } = await import(pathToFileURL(require.resolve("vite")).href);
process.chdir(process.env.VERIFY_EMPTY_ENV_DIR);
await build({
  root: directory,
  configFile: path.join(directory, "vite.config.ts"),
  envDir: process.env.VERIFY_EMPTY_ENV_DIR,
  mode: "production",
});
