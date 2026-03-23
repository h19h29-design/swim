# Repo Probe Commands for Codex CLI

Run these in the project root.

```bash
cd D:\gpt\01project\swimming-diary-dashboard

pwd

dir

rg -n "tesseract|easyocr|paddleocr|ocr" -S .
rg -n "fastapi|flask|django|streamlit|gradio|react|next|vite|svelte|vue" -S .
rg -n "include|exclude|reason|score" -S .
rg -n "local_samples|images" -S .
rg -n "PROJECT_CONTEXT|OCR_STRATEGY|TODO_NEXT" -S .
```

## What to capture
- OCR engine library names
- entrypoint for OCR processing
- backend framework
- frontend framework
- file where include/exclude is decided
- file where UI shows include/exclude

## Next Codex prompt
```text
Read PROJECT_CONTEXT.md, OCR_STRATEGY.md, and TODO_NEXT.md first.
Then inspect the repo using the findings above.
Do P0 only and report exact files that need patching next.
```
