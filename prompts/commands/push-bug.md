Push one already-drafted bug report to GitLab as an issue, via the `gitlab-publisher` subagent.

**Argument (bug slug, matching `output/bugs/<slug>.md`):** $ARGUMENTS

If no argument was given, ask which bug slug to push — do not guess or push every bug in the
run folder.

Invoke the `gitlab-publisher` subagent, telling it exactly which slug to push. Let it read the
draft, create the GitLab issue, and write the resulting issue reference back into the local
file. Report back the GitLab issue URL it returns.

This is a single, explicit push of one bug — never chain this into `/qa-pipeline` or invoke it
for more than the one slug given.
