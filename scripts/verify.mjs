import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  classify,
  extractPython,
  root,
  staticContracts,
} from "./verify/contracts.mjs";
import {
  isolatedEnvironment,
  preparedPackageManagers,
} from "./verify/environment.mjs";

const args = process.argv.slice(2);
const verificationStarted = Date.now();
if (args.includes("--help")) {
  console.log(
    "pnpm verify [--strict] [--full] [--only=backend,frontend,mobile,electron,worker] [--report=path]\nDefault: offline contracts + checker self-tests + in-memory API/client probes.\n--full: declared full-offline profile, not PG/runtime/native/production. Exit 0 scoped checks pass (known differences remain WARN); 1 new/stale difference or test failure; 2 blocked/missing dependency or skipped applicable tests. No installation, ports, platform calls or migration.\n--strict: every known contract difference also fails. --only selects full-profile suites; quick checks always run.",
  );
  process.exit(0);
}
for (const arg of args)
  if (
    !["--strict", "--full"].includes(arg) &&
    !arg.startsWith("--only=") &&
    !arg.startsWith("--report=")
  )
    throw new Error("Unknown verify option; use --help");
const full = args.includes("--full"),
  strict = args.includes("--strict");
if (!full && args.some((arg) => arg.startsWith("--only=")))
  throw new Error("--only requires --full");
const suites = args
  .find((x) => x.startsWith("--only="))
  ?.slice(7)
  .split(",") ?? ["backend", "frontend", "mobile", "electron", "worker"];
if (
  suites.some(
    (x) => !["backend", "frontend", "mobile", "electron", "worker"].includes(x),
  )
)
  throw new Error("Unknown full-offline suite");
const temporary = mkdtempSync(path.join(os.tmpdir(), "control-center-verify-"));
const env = isolatedEnvironment(temporary);
writeFileSync(env.npm_config_userconfig, "");
writeFileSync(env.npm_config_globalconfig, "");
const pnpm = process.env.npm_execpath;
const python = (suite = "backend") =>
  process.env[`VERIFY_${suite.toUpperCase()}_PYTHON`] ??
  (existsSync(
    path.join(
      root,
      suite,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    ),
  )
    ? path.join(
        root,
        suite,
        process.platform === "win32"
          ? ".venv/Scripts/python.exe"
          : ".venv/bin/python",
      )
    : "python");
env.VERIFY_AST_PYTHON = python();
const report = {
  profile: full ? "full-offline" : "quick-offline",
  strict,
  steps: [],
  contracts: null,
  tools: {
    node: process.version,
    declaredPackageManager: JSON.parse(
      readFileSync(path.join(root, "package.json"), "utf8"),
    ).packageManager,
    actualPackageManager: null,
  },
  notRun: [
    "local/shared/production PostgreSQL and migrations",
    "container/runtime/real platform/native Electron/visual E2E",
    ...(full && suites.includes("backend")
      ? [
          "backend/tests/test_douyin_signer_runtime.py (opens ports; original CI retains it)",
          "backend/tests/test_notification_webhook_e2e.py (opens ports; original CI retains it)",
        ]
      : []),
    ...(full
      ? ["backend", "frontend", "mobile", "electron", "worker"]
          .filter((x) => !suites.includes(x))
          .map((x) => `${x} full suite not selected`)
      : ["five full validation suites (use --full)"]),
  ],
};
let blocked = false,
  failed = false;
function run(
  name,
  executable,
  parameters,
  cwd = temporary,
  prerequisite = false,
) {
  const started = Date.now();
  console.log(`\n[verify] ${name}`);
  const result = spawnSync(executable, parameters, {
    cwd,
    env,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
  const output = (result.stdout ?? "") + (result.stderr ?? "");
  process.stdout.write(output);
  const missing =
    !!result.error ||
    (prerequisite && result.status !== 0) ||
    /No module named|Cannot find package|Cannot find module|command not found/i.test(
      output,
    );
  const skipped = /(?:^|\n).*\b[1-9]\d* skipped\b|# skipped [1-9]\d*/m.test(
    output,
  );
  const state = missing
    ? "BLOCKED"
    : result.status !== 0
      ? "FAIL"
      : skipped
        ? "INCOMPLETE"
        : "PASS";
  blocked ||= missing || skipped;
  failed ||= !missing && result.status !== 0;
  const summary = output
    .split(/\r?\n/)
    .filter((line) =>
      /^\s*(?:Test Files|Tests\s|\d+ passed|#\s*(?:tests|pass|fail|skipped)|ℹ\s*(?:tests|pass|fail|skipped)|✓ built in)/u.test(
        line,
      ),
    )
    .slice(-20);
  report.steps.push({
    name,
    state,
    exitCode: result.status,
    seconds: Math.round((Date.now() - started) / 10) / 100,
    summary,
  });
  return { ok: result.status === 0 && !missing, output: result.stdout ?? "" };
}
function packageRun(project, script, extra = []) {
  if (!pnpm || !existsSync(pnpm)) {
    blocked = true;
    report.steps.push({
      name: `${project}:${script}`,
      state: "BLOCKED",
      reason: "Use pnpm verify; pnpm runner not found",
    });
    return { ok: false };
  }
  env.VERIFY_PROJECT = project;
  return run(
    `${project}:${script}`,
    process.execPath,
    [
      pnpm,
      "--pm-on-fail=ignore",
      "--dir",
      path.join(root, project),
      script,
      ...extra,
    ],
    root,
  );
}
try {
  if (pnpm && existsSync(pnpm)) {
    const version = run(
      "installed package manager (no preparation)",
      process.execPath,
      [pnpm, "--pm-on-fail=ignore", "--version"],
    );
    if (version.ok) report.tools.actualPackageManager = version.output.trim();
  }
  const backendReady = run(
    "offline Python prerequisites",
    python(),
    [
      "-I",
      "-c",
      'import sys; assert sys.version_info >= (3,12); import pytest, httpx, sqlalchemy, pydantic, cryptography; print("Python dependencies available")',
    ],
    temporary,
    true,
  );
  if (backendReady.ok) {
    run("checker negative self-tests", process.execPath, [
      "--test",
      path.join(root, "scripts/verify/contracts.test.mjs"),
    ]);
    run("Python AST extractor self-tests", python(), [
      "-I",
      "-S",
      path.join(root, "scripts/verify/python-contracts-test.py"),
    ]);
    try {
      const started = Date.now();
      const staticResult = staticContracts(
        extractPython(python(), { env, cwd: temporary }),
      );
      report.steps.push({
        name: "authority/consumer AST checks",
        state: "EXECUTED",
        seconds: (Date.now() - started) / 1000,
      });
      const probe = run("formal ASGI envelope probe", python(), [
        "-I",
        path.join(root, "scripts/verify/python-runner.py"),
        "probe",
      ]);
      const clients = packageRun("frontend", "exec", [
        "vitest",
        "run",
        "--config",
        "verify.config.ts",
      ]);
      {
        const findings = [...staticResult.findings];
        if (probe.ok) findings.push(...JSON.parse(probe.output));
        else blocked = true;
        if (clients.ok && existsSync(env.VERIFY_PROBE_OUTPUT))
          findings.push(
            ...JSON.parse(readFileSync(env.VERIFY_PROBE_OUTPUT, "utf8")),
          );
        else blocked = true;
        const exceptions = strict
          ? []
          : JSON.parse(
              readFileSync(
                path.join(root, "scripts/verify/known-differences.json"),
                "utf8",
              ),
            );
        const result = classify(findings, exceptions);
        report.contracts = { ...result, coverage: staticResult.coverage };
        for (const row of result.known)
          console.log(`[KNOWN NOT FIXED] ${JSON.stringify(row)}`);
        for (const row of result.failures)
          console.log(`[CONTRACT FAIL] ${JSON.stringify(row)}`);
        for (const row of result.stale)
          console.log(`[STALE EXCEPTION] ${JSON.stringify(row)}`);
        failed ||= result.failures.length > 0 || result.stale.length > 0;
      }
    } catch (error) {
      blocked = true;
      report.steps.push({
        name: "contract prerequisites",
        state: "BLOCKED",
        reason: error.message,
      });
      console.error(error.message);
    }
  } else {
    report.steps.push({
      name: "offline contracts and their self-tests",
      state: "BLOCKED",
      reason: "Python prerequisite unavailable; not executed",
    });
  }
  if (full)
    for (const suite of suites) {
      if (["backend", "worker"].includes(suite)) {
        run(`${suite}:existing pytest (offline profile)`, python(suite), [
          "-I",
          path.join(root, "scripts/verify/python-runner.py"),
          suite,
        ]);
      } else {
        if (suite !== "electron") packageRun(suite, "lint");
        packageRun(suite, "typecheck");
        packageRun(
          suite,
          "test",
          suite === "electron"
            ? []
            : ["--config", path.join(root, "scripts/verify/unit.config.ts")],
        );
        if (suite !== "electron")
          run(
            `${suite}:Real production build (existing Vite config; no env files)`,
            process.execPath,
            [path.join(root, "scripts/verify/build.mjs"), suite],
          );
        // Electron's existing test script already performs its TypeScript build;
        // it runs Node tests, not the Electron executable or Windows packaging.
      }
    }
} finally {
  const prepared = preparedPackageManagers(temporary);
  report.packageManagerPreparation = { checked: true, detected: prepared };
  if (prepared.length) {
    failed = true;
    report.steps.push({
      name: "package manager isolation",
      state: "FAIL",
      reason: "Unexpected package manager preparation in private cache",
    });
  }
  try {
    // Only our concrete mkdtemp directory, never a workspace or shared runtime.
    if (
      path.dirname(temporary) !== os.tmpdir() ||
      !path.basename(temporary).startsWith("control-center-verify-")
    )
      throw new Error("unsafe-target");
    rmSync(temporary, { recursive: true, force: true });
  } catch (error) {
    blocked = true;
    report.steps.push({
      name: "temporary cleanup",
      state: "BLOCKED",
      reason: error.code ?? "unsafe-target",
    });
  }
  report.exitCode = failed ? 1 : blocked ? 2 : 0;
  report.totalSeconds =
    Math.round((Date.now() - verificationStarted) / 10) / 100;
  report.result = failed
    ? "FAIL"
    : blocked
      ? "BLOCKED_OR_INCOMPLETE"
      : report.contracts?.known.length
        ? "SCOPED_CHECKS_PASS_WITH_KNOWN_DIFFERENCES"
        : "SCOPED_CHECKS_PASS";
  console.log(
    `\n[verify] ${report.result}; known-not-fixed=${report.contracts?.known.length ?? 0}; exit=${report.exitCode}`,
  );
  for (const reason of report.notRun) console.log(`[NOT_RUN] ${reason}`);
  const destination = args.find((x) => x.startsWith("--report="))?.slice(9);
  if (destination) {
    const file = path.resolve(root, destination);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, JSON.stringify(report, null, 2) + "\n");
  }
  process.exitCode = report.exitCode;
}
