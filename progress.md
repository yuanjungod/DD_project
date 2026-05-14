# Progress

## 2026-05-14
- Started cleanup task focused on file-backed configuration and resource sources.
- Implemented lazy legacy YAML loading in agent workflow runtime.
- Added file-backed loaders/sync for skill packages and tool configs.
- Removed unused `SkillConfig` ORM model/export.
- Reworked frontend workflow display names to come from API templates instead of static IDs.
- Updated docs and legacy YAML comments to clarify bundle/file-backed authority.
- Verification: Python syntax check passed; frontend `npx tsc --noEmit` passed; IDE lints clean.
