import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = fileURLToPath(new URL("../../", import.meta.url));
const pc = "frontend/src/entities/",
  mobile = "mobile/src/entities/";
const backend = "backend/app/modules/";
const enumRef = (domain, name) => [`${backend}${domain}/enums.py`, name];
const dtoRef = (domain, name) => [`${backend}${domain}/schemas.py`, name];
const taskConsumers = ["frontend", "mobile"].map(
  (client) => `${client}/src/entities/task/api/contracts.ts`,
);

// Deliberately explicit coverage, not a claim to scan/generate every API.
export const manifest = {
  enums: [
    ...taskConsumers.flatMap((file) => [
      [enumRef("tasks", "TaskStatus"), [file, "TaskStatusDto"]],
      [enumRef("tasks", "TaskEventType"), [file, "TaskEventTypeDto"]],
    ]),
    [
      enumRef("audit", "AuditAction"),
      [`${pc}audit-log/model/types.ts`, "AuditAction"],
    ],
    [
      enumRef("audit", "AuditTargetType"),
      [`${pc}audit-log/model/types.ts`, "AuditTargetType"],
    ],
    [
      enumRef("workers", "SkillClassification"),
      [`${mobile}device/api/contracts.ts`, "DeviceSkillClassificationDto"],
    ],
    [
      enumRef("workers", "WorkerConnectionStatus"),
      [`${mobile}device/api/contracts.ts`, "DeviceConnectionStatusDto"],
    ],
    [
      enumRef("operating_dashboard", "OperatingCollectionJobStatus"),
      [
        "frontend/src/features/operating-dashboard/api/operating-dashboard-api.ts",
        "OperatingDashboardCollectionJobDto",
        "status",
      ],
    ],
    [
      enumRef("operating_dashboard", "OperatingCollectionItemStatus"),
      [
        "frontend/src/features/operating-dashboard/api/operating-dashboard-api.ts",
        "OperatingDashboardCollectionItemDto",
        "status",
      ],
    ],
  ],
  maps: [
    [
      enumRef("audit", "AuditAction"),
      [`${pc}audit-log/model/types.ts`, "ACTION_LABELS"],
    ],
    [
      enumRef("audit", "AuditTargetType"),
      [`${pc}audit-log/model/types.ts`, "TARGET_LABELS"],
    ],
    ...["frontend", "mobile"].map((client) => [
      enumRef("tasks", "TaskStatus"),
      [`${client}/src/entities/task/model/status-meta.ts`, "TASK_STATUS_META"],
    ]),
  ],
  dtos: [
    [
      dtoRef("audit", "AuditLogRead"),
      [`${pc}audit-log/api/contracts.ts`, "AuditLogReadDto"],
    ],
    [
      dtoRef("audit", "AuditLogRead"),
      [`${pc}audit-log/model/types.ts`, "AuditLogViewModel"],
      { team_id: "teamId" },
    ],
    [
      dtoRef("access", "MyTeamMembershipRead"),
      [`${mobile}human-auth/api/contracts.ts`, "HumanTeamMembershipDto"],
    ],
    ...["frontend", "mobile"].flatMap((client) => [
      [
        dtoRef("devices", "DeviceRead"),
        [`${client}/src/entities/device/api/contracts.ts`, "DeviceReadDto"],
      ],
      [
        dtoRef("workers", "YingdaoProviderInventory"),
        [
          `${client}/src/entities/device/api/contracts.ts`,
          client === "frontend"
            ? "YingdaoProviderInventoryDto"
            : "YingdaoProviderInventoryReadDto",
        ],
      ],
      [
        dtoRef("workers", "DeviceSkillCapabilityRead"),
        [
          `${client}/src/entities/device/api/contracts.ts`,
          "DeviceSkillCapabilityReadDto",
        ],
      ],
      [
        dtoRef("tasks", "TaskListItemRead"),
        [`${client}/src/entities/task/api/contracts.ts`, "TaskListItemReadDto"],
      ],
      [
        ["backend/app/core/exceptions/handlers.py", "ErrorResponse"],
        [`${client}/src/shared/api/contracts.ts`, "ApiErrorResponseDto"],
      ],
    ]),
  ],
  enumFields: [
    ["OperatingDataCollectionJobRead", "kind", "OperatingCollectionJobKind"],
    [
      "OperatingDataCollectionJobRead",
      "status",
      "OperatingCollectionJobStatus",
    ],
    [
      "OperatingDataCollectionItemRead",
      "status",
      "OperatingCollectionItemStatus",
    ],
    [
      "OperatingDataCollectionItemRead",
      "failure_stage",
      "OperatingCollectionFailureStage",
    ],
  ],
};

export function finding(rule, contract, expected, actual) {
  return { rule, contract, expected, actual };
}

export function enumFindings(contract, expected, actual, subset = false) {
  const missing = subset
    ? []
    : expected.filter((value) => !actual.includes(value));
  const extra = actual.filter((value) => !expected.includes(value));
  return [
    ...missing.map((value) =>
      finding("enum-missing", contract, value, "missing"),
    ),
    ...extra.map((value) =>
      finding("enum-extra", contract, "declared server value", value),
    ),
  ];
}

export function fieldFindings(contract, server, client) {
  if (!client) return [finding("field-missing", contract, server, "missing")];
  if (
    server.some((atom) => atom.startsWith("unsupported:")) ||
    client.some((atom) => atom.startsWith("unsupported:"))
  )
    return [finding("unsupported-field-type", contract, server, client)];
  const wide = client.includes("any") || client.includes("unknown");
  if (server.includes("null") && !client.includes("null") && !wide)
    return [finding("nullable-narrowed", contract, server, client)];
  const accepted = (value) =>
    wide ||
    client.includes(value) ||
    (value.startsWith("literal:") && client.includes("string")) ||
    (value.startsWith("literal_number:") && client.includes("number")) ||
    (value.startsWith("literal_boolean:") && client.includes("boolean")) ||
    (["object", "array"].includes(value) && client.includes("nonprimitive"));
  return server.some((value) => !accepted(value))
    ? [finding("type-narrowed", contract, server, client)]
    : [];
}

export function classify(findings, exceptions = []) {
  const signature = (value) =>
    JSON.stringify([value.rule, value.contract, value.expected, value.actual]);
  const known = new Map(exceptions.map((entry) => [signature(entry), entry]));
  if (
    known.size !== exceptions.length ||
    exceptions.some((x) => !x.reason || !x.review)
  )
    throw new Error(
      "Exceptions require unique exact evidence, reason and explicit review",
    );
  const observed = new Set(findings.map(signature));
  return {
    failures: findings.filter((entry) => !known.has(signature(entry))),
    known: findings.filter((entry) => known.has(signature(entry))),
    stale: exceptions.filter((entry) => !observed.has(signature(entry))),
  };
}

export function typescriptSnapshot(paths, sources = new Map()) {
  const require = createRequire(path.join(root, "frontend/package.json"));
  const ts = require("typescript");
  const options = {
    strictNullChecks: true,
    target: ts.ScriptTarget.ESNext,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    baseUrl: path.join(root, "frontend"),
    paths: { "@/*": ["src/*"] },
    skipLibCheck: true,
  };
  const host = ts.createCompilerHost(options),
    read = host.readFile.bind(host);
  const exists = host.fileExists.bind(host),
    getSource = host.getSourceFile.bind(host);
  host.readFile = (file) => sources.get(path.normalize(file)) ?? read(file);
  host.fileExists = (file) => sources.has(path.normalize(file)) || exists(file);
  host.getSourceFile = (file, languageVersion, ...args) =>
    sources.has(path.normalize(file))
      ? ts.createSourceFile(
          file,
          sources.get(path.normalize(file)),
          languageVersion,
          true,
        )
      : getSource(file, languageVersion, ...args);
  const program = ts.createProgram(
    paths.map((p) => path.resolve(root, p)),
    options,
    host,
  );
  const checker = program.getTypeChecker(),
    result = {};
  const atoms = (type) => {
    if (type.isUnion()) {
      const values = new Set(type.types.flatMap(atoms));
      if (
        values.has("literal_boolean:true") &&
        values.has("literal_boolean:false")
      ) {
        values.delete("literal_boolean:true");
        values.delete("literal_boolean:false");
        values.add("boolean");
      }
      return [...values].sort();
    }
    const f = type.flags;
    if (f & ts.TypeFlags.Null) return ["null"];
    if (f & ts.TypeFlags.Undefined) return ["undefined"];
    if (f & ts.TypeFlags.StringLiteral) return [`literal:${type.value}`];
    if (f & ts.TypeFlags.NumberLiteral) return [`literal_number:${type.value}`];
    if (f & ts.TypeFlags.BooleanLiteral)
      return [`literal_boolean:${type.intrinsicName}`];
    if (f & ts.TypeFlags.String) return ["string"];
    if (f & ts.TypeFlags.NumberLike) return ["number"];
    if (f & ts.TypeFlags.BooleanLike) return ["boolean"];
    if (f & ts.TypeFlags.Any)
      return [
        type.intrinsicName === "error"
          ? "unsupported:unresolved-client"
          : "any",
      ];
    if (f & ts.TypeFlags.Unknown) return ["unknown"];
    if (f & ts.TypeFlags.NonPrimitive) return ["nonprimitive"];
    if (checker.isArrayType(type) || checker.isTupleType(type))
      return ["array"];
    return ["object"];
  };
  for (const file of paths) {
    const source = program.getSourceFile(path.resolve(root, file));
    if (!source) throw new Error(`Missing contract file: ${file}`);
    const declarations = {};
    const visit = (node) => {
      if (
        (ts.isInterfaceDeclaration(node) ||
          ts.isTypeAliasDeclaration(node) ||
          ts.isVariableDeclaration(node)) &&
        node.name &&
        ts.isIdentifier(node.name)
      ) {
        const type = checker.getTypeAtLocation(node.name);
        declarations[node.name.text] = {
          atoms: atoms(type),
          fields: Object.fromEntries(
            checker
              .getPropertiesOfType(type)
              .map((property) => [
                property.name,
                atoms(
                  checker.getTypeOfSymbolAtLocation(
                    property,
                    property.valueDeclaration ?? node,
                  ),
                ),
              ]),
          ),
        };
        if (ts.isVariableDeclaration(node) && node.initializer) {
          let value = node.initializer;
          while (
            ts.isAsExpression(value) ||
            ts.isSatisfiesExpression(value) ||
            ts.isParenthesizedExpression(value)
          )
            value = value.expression;
          if (ts.isObjectLiteralExpression(value))
            declarations[node.name.text].mappingKeys = checker
              .getPropertiesOfType(checker.getTypeAtLocation(value))
              .map((p) => p.name);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
    result[file] = declarations;
  }
  return result;
}

export function staticContracts(python) {
  const pairs = [...manifest.enums, ...manifest.maps, ...manifest.dtos];
  const paths = [...new Set(pairs.map(([, target]) => target[0]))];
  const consumer = typescriptSnapshot(paths),
    findings = [];
  const authority = ([file, name]) => {
    const value = python[file]?.[name];
    if (!value) throw new Error(`Missing authority: ${file}:${name}`);
    return value;
  };
  for (const [server, target] of manifest.enums) {
    const type = consumer[target[0]]?.[target[1]];
    if (!type) throw new Error(`Missing consumer: ${target.join(":")}`);
    const values = (target[2] ? type.fields[target[2]] : type.atoms)
      .filter((x) => x !== "null" && x !== "undefined")
      .map((x) => x.replace(/^literal:/, ""));
    findings.push(
      ...enumFindings(target.join(":"), authority(server).values, values),
    );
  }
  for (const [server, target] of manifest.maps) {
    const type = consumer[target[0]]?.[target[1]];
    if (!type?.mappingKeys)
      throw new Error(`Missing literal display mapping: ${target.join(":")}`);
    findings.push(
      ...enumFindings(
        target.join(":"),
        authority(server).values,
        type.mappingKeys,
      ),
    );
  }
  for (const [server, target, rename] of manifest.dtos) {
    const fields = consumer[target[0]]?.[target[1]]?.fields;
    if (!fields) throw new Error(`Missing DTO: ${target.join(":")}`);
    for (const [name, declaration] of Object.entries(
      authority(server).fields,
    )) {
      // ViewModel check is an explicit field mapping, not a DTO-generation claim.
      if (rename && !Object.hasOwn(rename, name)) continue;
      const clientName = rename?.[name] ?? name;
      let expected = declaration.atoms;
      expected = expected.flatMap((atom) => {
        if (!atom.startsWith("ref:")) return [atom];
        const name = atom.slice(4);
        const imported = python[server[0]].__imports__?.[name];
        const importedFile = imported?.[0].startsWith("app.")
          ? `backend/${imported[0].replaceAll(".", "/")}.py`
          : null;
        const referenced =
          python[server[0]][name] ?? python[importedFile]?.[imported?.[1]];
        if (!referenced) return [`unsupported:unresolved-authority:${name}`];
        return referenced.is_enum
          ? referenced.values.map((value) => `literal:${value}`)
          : ["object"];
      });
      findings.push(
        ...fieldFindings(
          `${target.join(":")}.${clientName}`,
          expected,
          fields[clientName],
        ),
      );
    }
  }
  for (const [type, field, enumName] of manifest.enumFields) {
    const source = ["backend/app/modules/operating_dashboard/schemas.py", type];
    const declaration = authority(source).fields[field];
    if (!declaration?.atoms.includes(`ref:${enumName}`))
      findings.push(
        finding(
          "unbound-authority-enum",
          `${source.join(":")}.${field}`,
          enumName,
          declaration?.annotation ?? "missing",
        ),
      );
  }
  return {
    findings,
    coverage: {
      enums: manifest.enums.length,
      mappings: manifest.maps.length,
      dtos: manifest.dtos.length,
      enumBindings: manifest.enumFields.length,
    },
  };
}

export function pythonPaths() {
  return [
    ...new Set(
      [...manifest.enums, ...manifest.maps, ...manifest.dtos]
        .map(([source]) => source[0])
        .concat(
          "backend/app/modules/operating_dashboard/schemas.py",
          "backend/app/modules/access/enums.py",
        ),
    ),
  ];
}

export function extractPython(python, options = {}) {
  const result = spawnSync(
    python,
    ["-I", "-S", path.join(root, "scripts/verify/python-contracts.py")],
    {
      input: JSON.stringify(
        options.sources
          ? { sources: options.sources }
          : { paths: pythonPaths() },
      ),
      encoding: "utf8",
      cwd: options.cwd ?? root,
      env: options.env ?? {
        PATH: process.env.PATH,
        SystemRoot: process.env.SystemRoot,
      },
    },
  );
  if (result.error || result.status !== 0)
    throw new Error("Python AST extractor failed; Python 3.12+ is required");
  return JSON.parse(result.stdout);
}
