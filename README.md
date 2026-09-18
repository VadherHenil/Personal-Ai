# Personal AI

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=microsoft" alt="Windows" />
  <img src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-EF9421?style=for-the-badge" alt="CC BY-NC 4.0" />
  <img src="https://img.shields.io/badge/Status-Active-00C853?style=for-the-badge" alt="Status Active" />
</p>

<p align="center">
  <strong>Voice-first desktop AI assistant for personal productivity, automation, and local control.</strong>
</p>

Personal AI is a powerful desktop assistant built to act like a smart, always-available personal system for daily workflows. It combines voice interaction, memory, automation, browser control, file handling, workflow planning, and a web dashboard into a single local AI experience.

## ✨ Highlights

- Voice-driven conversational assistant powered by Gemini
- Local personalization and memory for recurring user preferences
- Browser and desktop control for real task automation
- File, app, reminder, system monitoring, and workflow actions
- Optional dashboard for monitoring and management
- Desktop-first architecture designed for Windows workflows
- Extensible tool registry with modular action system

---

## 🚀 Features

### AI & Conversations
- Natural voice-first UI with real-time assistant interaction
- Gemini-backed reasoning and task execution
- Context-aware responses guided by memory and user personalization
- Session-based chat history and transcript support

### Productivity & Automation
- Open apps, manage files, search the web, and automate browser actions
- Weather, reminders, scheduling, and task planning support
- Desktop automation and screen capture utilities
- Optional proactive monitoring features and routine handling

### Memory & Personalization
- Saved user memory and profile-aware behavior
- App settings persistence in local config files
- Developer, research, household, and productivity skill profiles
- Long-term memory support for recurring context

### Security & Control
- Tool validation and runtime call checks
- Restricted execution policy for sensitive actions
- Safety-focused prompts and output sanitization

### Dashboard & UI
- Full desktop interface with rich theme system
- Optional web dashboard for monitoring and management
- Dynamic settings, personalization configuration, and status displays

---

## 🧩 Included Modules

This project includes a modular architecture with the following areas:

- `main.py` — application entry point and orchestration
- `ui.py` — desktop interface and interaction layer
- `tool_registry.py` — tool definitions and action registry
- `actions/` — voice and task actions for desktop, browser, files, weather, reminders, and more
- `memory/` — chat, memory, routines, and user profile management
- `core/` — LLM, planner, queueing, TTS/STT, logging, and installer support
- `dashboard/` — local dashboard server and static frontend
- `security/` — validation and control layer
- `config/` — app configuration and certificates
- `tests/` — project validation tests

---

## 🛠️ Requirements

- Python 3.11+
- Windows-focused desktop usage (primary target)
- A valid Gemini API key
- Optional extras for dashboard and browser automation

---

## ⚙️ Installation

### 1) Clone the repository

```bash
git clone https://github.com/<your-username>/Personal-Ai.git
cd Personal-Ai
```

### 2) Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3) Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4) Install optional extras

```bash
python -m pip install -e .[dashboard,windows,browser]
```

---

## 🔐 API Configuration

The app expects a Gemini API key. You can configure it in either of these ways:

### Option A: Environment variable

```bash
set GEMINI_API_KEY=your_api_key_here
```

### Option B: Config file

Copy the example config and update it:

```bash
copy config\api_keys.example.json config\api_keys.json
```

Then edit `config/api_keys.json` with your actual values.

---

## ▶️ Run the app

```bash
python main.py
```

This launches the desktop assistant interface and starts the assistant workflow.

---

## 📦 Build for Publishing

To build the project package locally:

```bash
python -m pip install build
python -m build
```

This creates distributable source and wheel archives in the `dist/` directory.

---

## 🧪 Testing

Run the included tests:

```bash
python -m pytest
```

The repository includes tests for chat storage, configuration, memory management, tool execution policy, and security controls.

---

## 📁 Project Structure

```text
Personal-Ai/
├── actions/
│   ├── background_monitor.py
│   ├── browser_control.py
│   ├── code_helper.py
│   ├── computer_control.py
│   ├── desktop.py
│   ├── dev_agent.py
│   ├── file_controller.py
│   ├── file_processor.py
│   ├── flight_finder.py
│   ├── game_updater.py
│   ├── open_app.py
│   ├── proactive.py
│   ├── reminder.py
│   ├── screen_processor.py
│   ├── send_message.py
│   ├── system_monitor.py
│   ├── weather_report.py
│   ├── web_search.py
│   └── youtube_video.py
├── config/
│   ├── api_keys.example.json
│   ├── api_keys.json
│   └── certs/
├── core/
│   ├── installer.py
│   ├── llm_client.py
│   ├── logging_utils.py
│   ├── prompt.txt
│   ├── stt.py
│   ├── task_planner.py
│   ├── tool_queue.py
│   ├── tts.py
│   └── update_checker.py
├── dashboard/
│   ├── server.py
│   └── static/
├── memory/
│   ├── action_store.py
│   ├── chat_store.py
│   ├── config_manager.py
│   ├── memory_manager.py
│   ├── routines.py
│   ├── transcripts/
│   ├── user_memory.py
│   └── long_term.json
├── security/
│   └── controls.py
├── tests/
├── LICENSE
├── README.md
├── main.py
├── pyproject.toml
├── requirements.txt
├── setup.py
├── tool_registry.py
├── ui.py
├── version.py
└── packaging/
```

---

## 🧠 Supported Actions

The assistant includes tools for:

- App launching and system actions
- Web search and news retrieval
- Weather reporting
- Browser automation and file operations
- Desktop and screen control
- Reminder creation and routine tracking
- Code assistance and developer tooling
- Game updater and system diagnostics
- Flight search and media lookup
- Memory and personalization management

---

## 🛡️ Security Notes

This project includes execution safety checks and permissions-based controls for tool usage. Sensitive operations are gated through validation layers before execution. Always review tool permissions before enabling automation features on a shared or production machine.

---

## 🧭 Roadmap Ideas

Planned improvements may include:

- More polished onboarding flow for new users
- Improved multi-language voice support
- Stronger plugin marketplace and extension model
- Better packaging and installer UX for end-user deployment
- Additional AI workflow templates and presets

---

## 🤝 Contributing

Contributions are welcome. If you want to improve the project:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a pull request with clear context and testing notes

---

## 📄 License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License.

See the [LICENSE](LICENSE) file for full details.

---

## ⭐ Final Note

Personal AI is designed to feel like a personal desktop copilot: useful, local, configurable, and built around everyday productivity. Whether used for automation, research, memory, or workflow help, the project is structured to grow into a much more capable personal assistant over time.
