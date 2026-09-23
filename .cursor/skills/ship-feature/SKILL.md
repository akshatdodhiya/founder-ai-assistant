---
name: ship-feature
description: Push local feature commits to remote and open a Pull Request via GitHub MCP with automated issue-closing links.
disable-model-invocation: true
---

# Ship Feature (Push & PR Creation)

Use this skill when local code and tests have been reviewed and approved by the human developer.

## Process

1. **Review Local History:**
   Run `git log main..HEAD --oneline` and `git diff main...HEAD`. Synthesize a clear overview of the changes.

2. **Push Branch to Remote:**
   Identify the current active branch and push it to `origin`:
   ```bash
   git push -u origin <current-branch-name>
   ```

3. **Create Pull Request via GitHub MCP:**
   Extract the issue number associated with this branch (e.g., Issue `#42`).
   Call the GitHub MCP `create_pull_request` tool with:
   - **Title:** `feat: <brief title>`
   - **Body:** Include a summary of changes, testing notes, and the binding link string:
     ```markdown
     ## Description
     <Summary changes of>

     ## Testing
     - Local Pytest runs passed.

     Closes #<issue_number>
     ```

4. **Provide PR Link & CI Status:**
   Output the created PR URL to the user. Inform them that the cloud CI pipeline is now triggered.

---

## CI Repair Protocol (If Cloud Tests Fail)

If the human user informs you that GitHub Actions CI failed on an active PR:
1. Use GitHub MCP tools (`get_job_logs` or PR checks API) to fetch the exact error logs from the failed CI run.
2. Analyze whether the failure is due to environment differences, missing dependencies, or unhandled OS constraints.
3. Apply the necessary fix to local code on the feature branch.
4. Run tests locally to verify.
5. Commit and push the fix:
   ```bash
   git commit -m "fix(ci): resolve cloud runner environment failure"
   git push origin <current-branch-name>
   ```
6. Notify the user that a repair commit has been pushed to the existing PR.
