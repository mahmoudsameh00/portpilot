// Creates the stack suite's identities on the isolated clone (dev/checks/api/Web_stack_fixture.py setup).
import { execFileSync } from "node:child_process";

export default function globalSetup() {
  execFileSync("uv", ["run", "python", "../dev/checks/api/Web_stack_fixture.py", "setup"], {
    stdio: "inherit",
  });
}
