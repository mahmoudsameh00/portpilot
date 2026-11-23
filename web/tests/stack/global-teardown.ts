// Removes the stack suite's identities and everything they made on the clone (Web_stack_fixture.py cleanup).
import { execFileSync } from "node:child_process";

export default function globalTeardown() {
  execFileSync("uv", ["run", "python", "../dev/checks/api/Web_stack_fixture.py", "cleanup"], {
    stdio: "inherit",
  });
}
