# JARVIS X - Known Issues

| Severity | Component | Description | Impact | Workaround | Recommended Fix |
|---|---|---|---|---|---|
| HIGH | Voice/STT | Background noise can sometimes trigger indefinite listening if VAD is overly sensitive. | STT hangs until explicit cancellation. | Speak clearly and use "Stop listening" command. | Tighten silence detection thresholds in VAD config. |
| MEDIUM | Model Router | Pynvml is not installed by default for VRAM detection on NVIDIA GPUs. | `ResourceManager` falls back to checking system RAM instead of VRAM. | None required (safely falls back). | Install `GPUtil` or `pynvml` automatically on Windows hosts. |
| LOW | Desktop/Vision | Screen capture OCR may fail to read heavily stylized fonts or dark-mode IDEs accurately. | Visual context slightly degraded. | Highlight text manually if JARVIS struggles to read it. | Upgrade OCR engine or rely on multimodal vision APIs when online. |
| LOW | Security Proxy | Interactive `input()` blocking during testing requires heavy `patch` mocks. | Test fragility. | Use `@patch('builtins.input', return_value='y')`. | Implement an explicit `test_mode=True` parameter in the config to bypass STDIN prompts in CI/CD. |
