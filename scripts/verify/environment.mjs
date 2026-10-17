import path from "node:path";

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
    npm_config_manage_package_manager_versions: "false",
    npm_config_package_manager_strict: "false",
    npm_config_offline: "true",
    npm_config_userconfig: path.join(temporary, "empty.npmrc"),
    npm_config_globalconfig: path.join(temporary, "empty-global.npmrc"),
  });
}
