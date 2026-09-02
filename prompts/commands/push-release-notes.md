Push the drafted release notes (`output/release-notes.md` for the current run) to GitLab as a
wiki page, via the `gitlab-publisher` subagent.

**Argument (version identifier, e.g. `3.0.68-DA`):** $ARGUMENTS

If no argument was given, ask for the version identifier — it's what names the wiki page
(`Version_History/<version>-Release` by default; configurable in
`config/pipeline.config.yaml`'s `gitlab.wiki_release_notes_dir`) and it's independent of
`run_id`, so it can't be defaulted or inferred.

Invoke the `gitlab-publisher` subagent, telling it exactly which version to publish under. Let
it read the draft, create (or, if explicitly told to force it, update) the wiki page, and write
the resulting wiki reference back into the local file. Report back the GitLab wiki URL it
returns.

This is a single, explicit push for one version — never chain this into `/qa-pipeline`.
