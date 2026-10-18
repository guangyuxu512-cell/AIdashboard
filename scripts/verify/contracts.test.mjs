import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import test from "node:test";
import {
  classify,
  enumFindings,
  fieldFindings,
  finding,
  root,
  typescriptSnapshot,
} from "./contracts.mjs";
import {
  isolatedEnvironment,
  preparedPackageManagers,
} from "./environment.mjs";
import { existsSync, mkdtempSync, mkdirSync, rmSync } from "node:fs";
import os from "node:os";

test("private package-manager guard detects a prepared installation, not metadata alone", () => {
  const temporary = mkdtempSync(
    path.join(os.tmpdir(), "verify-install-probe-"),
  );
  try {
    mkdirSync(path.join(temporary, "pnpm/v11/metadata"), { recursive: true });
    assert.deepEqual(preparedPackageManagers(temporary), []);
    mkdirSync(
      path.join(
        temporary,
        "pnpm/store/v11/links/@/pnpm/test/node_modules/pnpm",
      ),
      { recursive: true },
    );
    assert.equal(preparedPackageManagers(temporary).length, 1);
  } finally {
    assert.equal(path.dirname(temporary), os.tmpdir());
    assert.ok(path.basename(temporary).startsWith("verify-install-probe-"));
    rmSync(temporary, { recursive: true, force: true });
  }
});

test("Python AST and TS compiler feed real nonzero command exits for incompatible or unsupported fields", () => {
  const local = path.join(
    root,
    "backend",
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
  const python =
    process.env.VERIFY_AST_PYTHON ?? (existsSync(local) ? local : "python");
  for (const [server, client, expected] of [
    [
      "class Dto(BaseModel):\n kind: Literal['ok']",
      "interface Dto {kind:'other'}",
      1,
    ],
    [
      "class Dto(BaseModel):\n kind: dict[str,str]",
      "interface Dto {kind:string}",
      1,
    ],
    [
      "class Dto(BaseModel):\n kind: Callable[[str],int]",
      "interface Dto {kind:string}",
      1,
    ],
    [
      "class Dto(BaseModel):\n kind: Union[str,None]",
      "interface Dto {kind:string}",
      1,
    ],
    [
      "class Dto(BaseModel):\n request_id: str",
      "interface Dto {code:string}",
      1,
    ],
    [
      "class Dto(BaseModel):\n kind: Literal['ok']",
      "interface Dto {kind:string}",
      0,
    ],
  ]) {
    const code = `import path from 'node:path'; import {extractPython,typescriptSnapshot,fieldFindings,classify,root} from ${JSON.stringify(new URL("./contracts.mjs", import.meta.url).href)};const authority=extractPython(${JSON.stringify(python)},{sources:{'memory.py':${JSON.stringify(server)}}})['memory.py'].Dto.fields;const name='frontend/__verify_pipeline__.ts';const client=typescriptSnapshot([name],new Map([[path.join(root,name),${JSON.stringify(client)}]]))[name].Dto.fields;const findings=Object.entries(authority).flatMap(([name,field])=>fieldFindings('memory.'+name,field.atoms,client[name]));process.exit(classify(findings).failures.length?1:0)`;
    const result = spawnSync(
      process.execPath,
      ["--input-type=module", "-e", code],
      { encoding: "utf8", env: isolatedEnvironment(process.env.TEMP ?? root) },
    );
    assert.equal(result.status, expected, result.stderr);
  }
});

test("subprocesses receive synthetic configuration and cannot auto-install package managers", () => {
  const env = isolatedEnvironment("synthetic-temp", {
    PATH: "safe",
    BACKEND_DATABASE_URL: "forbidden",
    WORKER_DEVICE_TOKEN: "forbidden",
    GITHUB_TOKEN: "forbidden",
    VITE_SECRET: "forbidden",
  });
  assert.equal(env.PATH, "safe");
  assert.equal(JSON.stringify(env).includes("forbidden"), false);
  assert.equal(env.pnpm_config_pm_on_fail, "ignore");
  assert.equal(env.pnpm_config_verify_deps_before_run, "error");
  assert.equal(env.pnpm_config_offline, "true");
  assert.equal(env.APPDATA, "synthetic-temp");
});

test("offline subprocess timezone stays Shanghai under different host timezones", () => {
  const script = `console.log(JSON.stringify(['2026-08-18T10:00:00+00:00', '2026-08-18T11:00:00+00:00'].map(value => new Date(value).getHours())))`;
  for (const timezone of ["UTC", "America/Los_Angeles"]) {
    const source = { ...process.env, TZ: timezone };
    const env = isolatedEnvironment(os.tmpdir(), source);
    assert.equal(env.TZ, "Asia/Shanghai");
    assert.equal(source.TZ, timezone);
    const child = spawnSync(process.execPath, ["-e", script], {
      env,
      encoding: "utf8",
    });
    assert.equal(child.status, 0, child.stderr);
    assert.deepEqual(JSON.parse(child.stdout), [18, 19]);
  }
});

test("an added server state without a consumer fails with a nonzero process exit", () => {
  const code = `import {enumFindings,classify} from ${JSON.stringify(new URL("./contracts.mjs", import.meta.url).href)}; process.exit(classify(enumFindings('fixture',['pending','new_state'],['pending'])).failures.length ? 1 : 0)`;
  assert.equal(
    spawnSync(process.execPath, ["--input-type=module", "-e", code]).status,
    1,
  );
});
test("a swapped product-selection brand wire mapping fails with a nonzero process exit", () => {
  const code = `import {classify,finding} from ${JSON.stringify(new URL("./contracts.mjs", import.meta.url).href)};const expected={all:'-1',known:'1',unknown:'0'};const mutated={all:'-1',known:'0',unknown:'1'};const findings=Object.keys(expected).filter(key=>expected[key]!==mutated[key]).map(key=>finding('selection-brand-wire','product-selection:brand:'+key,expected[key],mutated[key]));process.exit(classify(findings).failures.length?1:0)`;
  assert.equal(
    spawnSync(process.execPath, ["--input-type=module", "-e", code]).status,
    1,
  );
});
test("normal and explicitly intentional subset consumers pass", () => {
  assert.deepEqual(enumFindings("fixture", ["created"], ["created"]), []);
  assert.deepEqual(
    enumFindings(
      "pc_schedule_subset",
      ["task_created", "blocked", "selection_run"],
      ["task_created", "blocked"],
      true,
    ),
    [],
  );
});
test("nullable narrowing and missing error fields are not swallowed", () => {
  assert.equal(
    fieldFindings("dto.nullable", ["string", "null"], ["string"])[0].rule,
    "nullable-narrowed",
  );
  assert.equal(
    fieldFindings("error.request_id", ["string"], undefined)[0].rule,
    "field-missing",
  );
  assert.deepEqual(
    fieldFindings("dto.zero", ["number"], ["number", "null"]),
    [],
  );
  for (const [server, client] of [
    [["string", "null"], ["string"]],
    [["string"], null],
  ]) {
    const code = `import {fieldFindings,classify} from ${JSON.stringify(new URL("./contracts.mjs", import.meta.url).href)};process.exit(classify(fieldFindings('fixture',${JSON.stringify(server)},${JSON.stringify(client)})).failures.length?1:0)`;
    assert.equal(
      spawnSync(process.execPath, ["--input-type=module", "-e", code]).status,
      1,
    );
  }
});
test("TypeScript compiler resolves aliases, null and boolean without truthiness or regex guesses", () => {
  const file = "frontend/__verify_memory__.ts";
  const source =
    'type State = "ok" | "new"; type Alias = State; interface Dto { value: 0 | number | null; flag: boolean | null }; const LABELS = {ok: "OK", new: "NEW"} as const; const INCOMPLETE: Record<State,string> = {ok:"OK"} as Record<State,string>';
  const snapshot = typescriptSnapshot(
    [file],
    new Map([[path.join(root, file), source]]),
  )[file];
  assert.deepEqual(snapshot.Alias.atoms, ["literal:new", "literal:ok"]);
  assert.deepEqual(snapshot.Dto.fields.value, ["null", "number"]);
  assert.deepEqual(snapshot.Dto.fields.flag, ["boolean", "null"]);
  assert.deepEqual(Object.keys(snapshot.LABELS.fields).sort(), ["new", "ok"]);
  assert.deepEqual(snapshot.INCOMPLETE.mappingKeys, ["ok"]);
  assert.equal(
    enumFindings("display", ["ok", "new"], snapshot.INCOMPLETE.mappingKeys)
      .length,
    1,
  );
});
test("known differences are exact, reviewed, never widened, and stale entries fail review", () => {
  const old = finding(
    "nullable-narrowed",
    "fixture",
    ["null", "string"],
    ["string"],
  );
  const exception = {
    ...old,
    reason: "known fixture only",
    review: "unit-test approval",
  };
  assert.equal(classify([old], [exception]).known.length, 1);
  assert.equal(
    classify([{ ...old, actual: ["boolean"] }], [exception]).failures.length,
    1,
  );
  assert.equal(classify([], [exception]).stale.length, 1);
  assert.throws(() => classify([old], [old]), /review/);
  assert.throws(() => classify([old], [exception, exception]), /unique/);
});
