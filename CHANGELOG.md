# Changelog

## 0.1.9.4

- LM Studio tool schemas send array `items` as a JSON Schema object again. `true` made the grammar parser return HTTP 400. A missing item schema is `{"type": "string"}`.
- Attachments and downloads no longer appear inside whatever folder is chosen as the workspace. `./attachments` and `./downloads` stay at the installed Kerniq root. Agent settings have their own path and Browse button. An absolute path is used as written.
- Explorer names that do not fit the pane end with an ellipsis. The workspace path in the top bar keeps the end of the path (the folder name) and puts the full path on hover.
- Host freedom is decided before the symlink walk and the other path locks. While the virtual environment is still on, absolute paths are shown but leaving them is still refused. Leaving is allowed only when host freedom is on and the virtual environment is off. Destructive commands stay denied.
- Folder space skips a zero-byte color, steps sizes at 1024 (797245 B is 778.5 KB), and shows the total, for example 778.5 KB / 12.0 GB. The folder-space hint is translated.

## 0.1.9.3

- Server mode runs different users at the same time. One user's next run waits until that user's previous run finishes.
- A server account can start 30 runs a minute. `rpm_limit` in the server settings changes it. Zero turns the limit off.
- Local providers (LM Studio, Ollama) are refused in server mode unless administrator debug mode is on.
- With an empty users root, server mode uses `/home/Kerniq/kerniq-workspace/<cookie>/` when that directory can be created. Each cookie gets `workspace`, `attachments`, `downloads`, `.kerniq-view`, and its own `.kerniq-venv`.
- Tools in one turn stay in order. Developer mode has "Run tools in parallel", and only then do they run together. Results are still written back in the original order.
- A timed-out or stopped shell is killed with its children. On Windows that is `taskkill /T /F`. On Linux the shell is its own process group.
- Turning a tool off is what the list shows, including tools that were already off. A disabled plugin's tools stay out of the live tool list.
- Show plan is on by default. Off hides the plan panel. On a narrow screen the panel stays above the chat and can be resized.
- Files in downloads that have not been touched for 30 days are removed. Workspace and attachments are not.

## Working tree after 0.1.9.1

- Choosing "all — no prompts" asks for a 3 second confirmation. Cancel puts the previous level back.
- Developer mode off hides the virtual environment and host freedom and resets them: virtual environment on, host freedom off. Developer mode on shows only the virtual environment. Turning that off asks for 3 seconds, then host freedom appears and stays off.
- Turning a plugin off hides its tools in the list immediately. Their saved settings stay. The next run does not register those tools.
- Workspace, attachments, and downloads each have a space limit. The default is 4 GB of space added after Kerniq first measured the folder. Existing files, including an existing `.git`, are the baseline. If the folder shrinks, the baseline drops and the used number stays at zero. The numbers live in `~/.kerniq` and file tools cannot read them.
- The explorer is three stacked panes. One is open. The choice is remembered.
- Clearing a folder asks for 3 seconds. Workspace clear leaves `.git`, the virtual environment, attachments, and downloads.
- The Git session plugin commits workspace changes at the end of a run. The model can restore one file or the whole session. A later commit that is not Kerniq's is not erased.
- If git is missing when the UI starts, Kerniq tries to install it and remembers that. Uninstall removes git only in that case, and also removes `.kerniq`, `.kerniq-view`, and `.kerniq-venv`.

## 0.1.9.1

Compared with GitHub Kerniq 0.1.8.

- `.kerniq-view` is three symlinks (`workspace`, `attachments`, `downloads`) and is created beside the workspace, never inside it. A nested view left in the project is removed. Listing `.` shows those three links. `file.txt`, `./file.txt`, and `workspace/file.txt` are the same file.
- The shell starts in that view. Host freedom keeps the host `PATH`, so `ls`, `cat`, and `sed` stay available. Leaving the virtual environment drops `VIRTUAL_ENV`.
- Context compaction writes the summary into the first system message and keeps the configured number of non-system messages, including the original request.
- The context length chosen in settings is sent when LM Studio loads a model. A different length reloads the model. An empty value leaves the model's own maximum.
- LM Studio tool schemas no longer put an object in a Jinja boolean test. Array `items` is `true`, and the item shape stays in the description.
- A tool call is shown immediately as "Waiting for a tool" / "Ожидание инструмента". The result updates that card. The next model turn waits until the tool returns.
- Chats are unlimited outside server mode. Server mode allows 3 and refuses a new one until a chat is deleted. Existing longer lists are not trimmed.
- Deleting a chat drops its memory, chat log, server replies, and `session-*.json` files tagged with that chat. Untagged session files older than an hour are removed. Files that cannot be tied to a deleted chat stay.
- `state/ui_chats.json` is saved through a unique temporary file under a lock.
- The Web UI listen line is printed once.
- In the agent layout, New file and New folder stay off the chat list.
- Tests that import office, advisor, or benchmark skip when those repositories are not checked out. Each plugin keeps its own tests.

Office 0.1.2 is a separate repository. It is not inside this archive.
