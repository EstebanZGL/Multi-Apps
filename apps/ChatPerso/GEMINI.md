# Jarvis AI (ChatPerso)

## Description
A unified AI assistant interface supporting both local LLMs (via Ollama) and cloud LLMs (via Google Gemini). It features a native CustomTkinter interface with a fallback to a web-based Streamlit version.

## Key Features
- **Dual Engine**: Automatically detects and lists models from Ollama (local) and Gemini (API key required).
- **Web Search**: Integrates `google.serper.dev` to allow LLMs to search the internet for up-to-date information.
- **File Parsing**: Users can attach PDF, Word (docx), and text files for context. Image attachments are supported for Gemini Vision.
- **Markdown Rendering**: Uses `tkhtmlview` and `markdown2` to render rich text, code blocks, and tables natively in CustomTkinter.
- **Chat History**: Saves and manages conversations as JSON files in the `conversations/` directory.