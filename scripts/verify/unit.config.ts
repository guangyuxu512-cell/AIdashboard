import pc from "../../frontend/vitest.config";
import mobile from "../../mobile/vitest.config";

// Reuse the original suites, aliases, Vue plugin and test env. Only Vite's
// dotenv directory changes to the runner's fresh empty directory.
const base = process.env.VERIFY_PROJECT === "frontend" ? pc : mobile;
if (
  !process.env.VERIFY_EMPTY_ENV_DIR ||
  !["frontend", "mobile"].includes(process.env.VERIFY_PROJECT ?? "")
)
  throw new Error("Use root verify with an explicit suite");
export default { ...base, envDir: process.env.VERIFY_EMPTY_ENV_DIR };
