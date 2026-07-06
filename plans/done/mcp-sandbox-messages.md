# MCP Sandbox Warning Messages — All Combinations

The `_AI_INSTRUCTION` prefix and `_EXPERIMENTAL_HEADER` are common to all four.

---

## Common prefix (all messages)

**⚠️ AI: You MUST show the following to the user as the last thing in your current response. ⚠️**

---

⚠️  **EXPERIMENTAL - USE WITH CAUTION**  ⚠️

The NEF-Pipelines MCP server is **EXPERIMENTAL software**. It is still under development!

---

## 1. Temporary sandbox (default, deleted at shutdown)

*Triggered by: `is_temporary=True, will_be_cleaned=True`*

The server is in **sandbox mode**. The AI is restricted to a single directory:

**`/tmp/nef_mcp_kx86bd4_`**

It can **READ, WRITE and OVERWRITE** files within this directory without further confirmation.

**⚠️ THE SANDBOX IS A TEMPORARY DIRECTORY AND WILL BE DELETED AT SERVER / AI SHUTDOWN.**
Ask the AI to change the sandbox to another directory if you want more permanent storage.

**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**

---

## 2. Temporary sandbox, preserved at shutdown (--preserve-sandbox)

*Triggered by: `is_temporary=True, will_be_cleaned=False`*

The server is in **sandbox mode**. The AI is restricted to a single directory:

**`/tmp/nef_mcp_kx86bd4_`**

It can **READ, WRITE and OVERWRITE** files within this directory without further confirmation.

**⚠️ THE SANDBOX WILL NOT BE CLEARED AT SHUTDOWN** (--preserve-sandbox was used). A new sandbox will be created on next server start. The sandbox may be cleared at computer reboot. This option is mainly present for debugging.

**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**

---

## 3. User defined sandbox (--path)

*Triggered by: `is_temporary=False, will_be_cleaned=False`, sandbox_path set*

The server is in **sandbox mode**. The AI is restricted to a single directory:

**`/Users/gary/my_nef_work`**

It can **READ, WRITE and OVERWRITE** files within this directory without further confirmation.

The server is using a **user defined sandbox** defined by the **--path** option or the environment variable xxx. The AI is restricted to this user supplied directory.

**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**

---

## 4. No sandbox (--no-sandbox)

*Triggered by: `no_sandbox=True`*

With **--no-sandbox** the AI has direct, unsupervised access to your filesystem and can
**READ, WRITE and OVERWRITE** files anywhere without further confirmation.

**BEFORE using this server you should:**
  - Ensure you restrict the server so it won't overwrite important files
    [are you using a container or an isolated server?]
  - Understand which AI model and client will connect
  - Never expose this server on a public network interface
  - Review the commands available via: `nef help commands`

**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**
