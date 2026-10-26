# Context Compact

This plugin ships with Kerniq. It is part of the default kit, together with the Web UI and the Plugin Manager. It is not installed or removed as an add-on. You can turn it off in its settings.

When the transcript reaches the trigger (a percent of the model window), the plugin asks the model to write a memory note of the older turns. The agent then receives:

1. the system prompt
2. that memory note
3. the original user goal
4. the last N messages, unchanged

The shrink target is either a percent of the window, and that percent must stay below the trigger, or a token count. Internal summarisation disables thinking so the budget is not spent on reasoning.

Settings: `enabled`, `trigger_percent`, `keep_last`, `target_mode`, `target_percent`, `target_tokens`. Change them in the Web UI Plugins section or with `kerniq plugins set`. If the plugin is disabled, Kerniq trims the window itself.
