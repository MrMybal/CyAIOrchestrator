---
id: backups
title: History, exports & backups
description: Preserve conversations without confusing them with project files.
section: Settings & maintenance
parent: settings
order: 24
revision: 1
---


1. Use history search for recorded messages, including archived conversations. Filter by project, provider, dates or status.
2. Export a conversation when you need its messages and mission records. Archive keeps it searchable; deleting is a separate action.
3. In Settings → Backup, export a portable backup or restore an existing one after reviewing the replacement confirmation.
4. Back up project folders separately. For a full local data-directory copy, stop the service first.

| Included or separate | What to expect |
| --- | --- |
| SQLite/application history | Recorded conversations, missions, references and application records. |
| Portable backup | Does not include credentials, project working files or provider-native session storage. Check media references and keep original files where needed. |
| Restore | Replaces local history after confirmation; a prior copy is kept. It does not roll project folders back. |
| Credentials | Windows DPAPI ties supported stored credentials to the Windows user. A copied data folder is not a portable login. |

[Open backup settings](doc:backups?app-settings=backup)

## Related chapters {#related}

- [Attachments, images & video](doc:files)
- [Projects & direct messages](doc:projects)
- [Troubleshooting](doc:troubleshooting)
