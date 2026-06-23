# Disclaimer

This project is for learning, experimentation, and creative coding.

It can create synthetic Git commits with custom author and committer dates. That
is useful for understanding how Git metadata works and for making harmless local
visual demos, but it can also be misused.

## Use Responsibly

Do not use this project to:

- Misrepresent real work.
- Inflate professional activity.
- Deceive recruiters, employers, collaborators, or open source maintainers.
- Pollute an existing project history.
- Bypass platform rules, policies, or community expectations.

If you publish a generated repository, make it clear that the history is a demo
or artwork.

If you use `--author-name` and `--author-email`, use your own identity or an
identity you are authorized to use. Do not attribute generated commits to
someone else.

## Safety Notes

The script includes guardrails:

- It only creates a new output directory when `--write-repo` is provided.
- It refuses to write into a non-empty output directory.
- It initializes a local repository itself.
- It checks that no Git remote is configured.
- It does not push, add remotes, open network connections, or authenticate with
  GitHub.
- It lets you choose the generated commit author explicitly with
  `--author-name` and `--author-email`.

Those guardrails are not a substitute for judgement. Read the command you are
running, choose an output directory you are comfortable creating, and inspect the
result before doing anything else with it.

## Publishing Notes

GitHub and other platforms may change how they display contribution activity.
They may also have policies or social norms around generated history. If you
publish the output, you are responsible for checking the current platform rules
and explaining the project honestly.

## No Warranty

This project is provided as-is. Use it at your own risk.
