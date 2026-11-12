# Skill Manager

Ships with Kerniq. It imports [Agent Skills](https://agentskills.io/specification): a folder with `SKILL.md`, optional `scripts/`, `references/`, and `assets/`. The same files are what Claude and other agents load from GitHub. Layouts differ. This plugin does not require one of them.

Accepted sources:

- `owner/repo` or `https://github.com/owner/repo`
- a file inside that repo: `owner/repo/skills/pdf`, or a GitHub `/tree/` or `/blob/` URL
- a local folder, a `.zip`, or the text of one `SKILL.md`
- a zip dropped into `skills/` next to `plugins/` (the zip is removed after a successful import)

Discovery looks for `SKILL.md` under `skills/`, `.claude/skills`, `.agents/skills`, `.github/skills`, `.cursor/skills`, `.codex/skills`, `.gemini/skills`, and `.opencode/skills`. A name that does not match the strict pattern is normalized, and the difference is reported. The skill is still imported.

Enabled skills are named in the system prompt. The instructions stay unloaded until the model calls `skill_load`. `skill_read` opens a file the skill points at. Scripts are not run by this plugin. The model uses the normal shell only when the skill says to and the user wants that work.

Skills already in the workspace are used in place. They are not copied. Removing one from Skill Manager does not delete the workspace copy.

Settings, Skill Manager, is a search field, Search, and Install, then the switches for how skills are offered, then the installed list. Each row shows the name and the repository, an on/off switch, and delete. The list updates as soon as you install, turn a skill on or off, or delete it. A skill that lives in the workspace cannot be deleted from this list. The same import, search, and on/off actions still exist as tools.
