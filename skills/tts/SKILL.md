---
name: tts
description: Generate outbound local TTS audio for Max with Windows System.Speech voices and global ffmpeg post-processing. Use when Max asks to answer by voice, generate TTS audio, test Pavel/Irina output, compare speaking rates, prepare Telegram-friendly OGG/Opus files, or create fallback WAV files. Default voice is Pavel, default rate is 3, and default output format is OGG.
---

# TTS

## Overview

Use the local Windows `System.Speech` path for offline speech generation.
Default voice is **Pavel**, default `Rate=3`, and default output is **OGG/Opus**.
Use **Irina** only when Max explicitly wants a female voice or a "secretary" persona.
Use global `ffmpeg` from `PATH` for OGG conversion.

## Workflow

1. Generate audio with `scripts/tts.ps1`.
2. Default to OGG output in `workspace/media/outbound` unless Max asks for another path or WAV.
3. If Max does not specify a rate, use the script default.
4. If Max asks for a female voice, set `-Voice irina`; otherwise keep `pavel`.
5. If a messaging send is needed, generate the file first, verify the output file exists, then send it separately.
6. For Telegram delivery, prefer OGG/Opus unless Max explicitly asks for WAV.
7. If Max explicitly asks to answer by voice, send voice-only output and do not add a duplicate text explanation unless he asks for both.
8. After a media send, verify success from the tool result before claiming it was sent.
9. If a send attempt times out, do not blindly retry; first consider possible late delivery and duplicate risk.

## Commands

### Default Pavel as OGG

```powershell
& '<skill-dir>\scripts\tts.ps1' -OutFile 'D:\Users\maxim\.openclaw\workspace\media\outbound\sample.ogg' -Text 'Привет, Max.'
```

### Explicit rate

```powershell
& '<skill-dir>\scripts\tts.ps1' -OutFile 'D:\Users\maxim\.openclaw\workspace\media\outbound\sample.ogg' -Text 'Привет, Max.' -Rate 3
```

### Irina voice

```powershell
& '<skill-dir>\scripts\tts.ps1' -OutFile 'D:\Users\maxim\.openclaw\workspace\media\outbound\sample.ogg' -Text 'Здравствуйте. Это тест Ирины.' -Voice irina
```

### Force WAV

```powershell
& '<skill-dir>\scripts\tts.ps1' -OutFile 'D:\Users\maxim\.openclaw\workspace\media\outbound\sample.wav' -Text 'Привет, Max.' -Format wav
```

## Voice rules

- `pavel` → default male Russian voice
- `irina` → female Russian voice
- valid rate range: `-10..10`
- current preferred default for Max: `Rate=3`
- default format: `ogg`
- fallback/editable format: `wav`

## Notes

- OGG mode synthesizes to a temporary WAV and removes it after conversion.
- Prefer OGG for Telegram/voice delivery.
- Prefer WAV only when Max explicitly wants a WAV artifact.
- If `System.Speech` stops seeing Pavel, verify the SAPI registry registration before changing the script.
- If OGG generation fails, verify that global `ffmpeg` is available in `PATH`.
