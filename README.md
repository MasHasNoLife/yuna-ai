# yuna-ai
A modular, locally-hosted AI VTuber pipeline.

Yuna is an autonomous, highly expressive AI VTuber designed to react to internet content, videos, and chat. Powered by local LLMs, multimodal vision processing, state-of-the-art offline TTS, and real-time Live2D/3D integration, this project orchestrates asynchronous text generation, frame-by-frame video analysis, audio transcription, and VTube Studio lip-sync into a seamless conversational pipeline.

Yuna is specifically prompted with a "Tsundere" personality matrix, utilizing structured emotional tags (e.g., `[flustered]`) to programmatically drive Text-to-Speech (TTS) emotion and VTube Studio facial expressions in real-time.

🧠 Core Architecture

The project is decoupled into interconnected microservices to ensure maximum efficiency and prevent VRAM bottlenecks on local hardware:

- **yuna.py (The Orchestrator):** The central asynchronous controller. It manages chat history, handles user commands, and streams AI responses token-by-token using the Ollama Python client to maintain low latency. It runs on a non-blocking asyncio event loop.
- **vision.py (The Eyes & Ears):** The multimodal processing engine. It utilizes OpenCV to extract video frames, ffmpeg and faster_whisper to transcribe audio, and a local Vision LLM (like LLaVA) to generate timestamped visual descriptions.
- **tts.py (The Voice):** Integrates the lightweight, ultra-fast `Kokoro-82M` text-to-speech engine. It dynamically strips performance tags from the LLM output and generates human-like vocal audio asynchronously via background threads to prevent WebSocket disconnects.
- **vts_link.py (The Avatar Link):** Connects directly to VTube Studio using their local WebSocket API (`pyvts`). It parses Yuna's emotional tags and translates them into corresponding expression or animation hotkey triggers inside VTube Studio.
- **yuna_prompt.py (The Personality Core):** A highly refined system instruction set. It forces the model to rely on specific behavioral loops and programmatic emotion tags that drive the `vts_link` layer.

⚙️ Tech Stack & Requirements

- **OS:** Arch Linux (Native pipeline) / Windows
- **AI Engine:** Ollama (Local API Endpoint)
- **Primary LLM:** Llama 3.1 (8B) for chat and personality orchestration
- **Vision LLM:** LLaVA (13B) / Llama 3.2-Vision for frame analysis
- **TTS Engine:** Kokoro-82M (PyTorch)
- **VTuber Software:** VTube Studio (with API access enabled)
- **Transcription:** faster-whisper (with CUDA fallback)
- **Core Dependencies:** Python 3, asyncio, opencv-python, ollama, pyvts, kokoro

🚀 Usage

You can launch Yuna in the terminal with optional modules enabled:
```bash
python yuna.py --tts --studio
```

Available commands during the chat loop:
- `/react` — Give a video file path for Yuna to watch and react to.
- `/video` — Manually paste a video description for Yuna to react to.
- `/reset` — Clear conversation history and start fresh.
- `exit` — Quit.