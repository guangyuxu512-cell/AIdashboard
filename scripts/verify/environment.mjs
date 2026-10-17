import path from "node:path";
import { existsSync, readdirSync } from "node:fs";

// Inspect only this invocation's empty-profile pnpm directory. Metadata/cache
// alone is not an install; executable/package trees must never be prepared.
export function preparedPackageManagers(temporary) {
  const detected = [];
  function inspect(directory) {
    if (!existsSync(directory)) return;
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const name = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        if (entry.name === "node_modules")
          detected.push(path.relative(temporary, name));
        else inspect(name);
      } else if (/^pnpm\.(?:cjs|mjs|exe)$/i.test(entry.name))
        detected.push(path.relative(temporary, name));
    }
  }
  inspect(path.join(temporary, "pnpm"));
  return detected;
}

export function isolatedEnvironment(temporary, source = process.env) {
  const env = {};
  for (const key of [
    "PATH",
    "Path",
    "SystemRoot",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "ProgramFiles",
    "ProgramFiles(x86)",
    "CI",
    "NO_COLOR",
    "FORCE_COLOR",
  ])
    if (source[key] !== undefined) env[key] = source[key];
  return Object.assign(env, {
    TEMP: temporary,
    TMP: temporary,
    APPDATA: temporary,
    LOCALAPPDATA: temporary,
    USERPROFILE: temporary,
    XDG_CONFIG_HOME: temporary,
    XDG_DATA_HOME: temporary,
    XDG_CACHE_HOME: temporary,
    VERIFY_EMPTY_ENV_DIR: temporary,
    VERIFY_PROBE_OUTPUT: path.join(temporary, "client-probes.json"),
    VITE_API_MODE: "real",
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONUTF8: "1",
    pnpm_config_pm_on_fail: "ignore",
    pnpm_config_runtime_on_fail: "error",
    pnpm_config_verify_deps_before_run: "error",
    pnpm_config_offline: "true",
    npm_config_userconfig: path.join(temporary, "empty.npmrc"),
    npm_config_globalconfig: path.join(temporary, "empty-global.npmrc"),
  });
}
