# DeepFaceLive bridge

This bridge exposes only local app status and start/stop controls. It does not upload or relay camera frames, audio, models, or output video. DeepFaceLive continues to use the input and models configured on the Windows computer.

## Connect a Windows computer

1. Connect the private **DeepFaceLive Setup Assistant** plugin to the Seldrune endpoint at `https://seldrune-platform.onrender.com/mcp/deepfacelive` and sign in with the Seldrune Owner account.
2. Call `pair_deepfacelive_agent` in the plugin and copy the one-time code. It expires after 10 minutes and can be used once.
3. On the Windows computer, install the companion dependency with `python -m pip install -r deepfacelive-agent-requirements.txt`, then run:

   ```powershell
   python deepfacelive_bridge_agent.py pair --server https://seldrune-platform.onrender.com --install-dir "D:\DeepFaceLive"
   python deepfacelive_bridge_agent.py run
   ```

   The pair command asks for the one-time code. It stores the resulting agent token encrypted with Windows DPAPI in the current user's `%APPDATA%` folder. Keep the run window open while you want remote control.

4. Use `deepfacelive_status`, `deepfacelive_start`, and `deepfacelive_stop` from the plugin. Start and stop requests are queued and can be checked with `deepfacelive_command_status`.

## Limits and safety

- The agent accepts only `start` and `stop`; no remote shell, arbitrary path, model, camera, or media-upload inputs are exposed.
- `start` launches the local `DeepFaceLive.bat`. Select cameras, source files, models, and output devices in the app itself.
- `stop` terminates only the process tree launched by this companion. If the companion exits, it leaves the app running.
- Pairing again replaces the previous agent token. Revoke access by removing the DeepFaceLive agent from the Seldrune owner console or rotating it with a new pairing code.
- Use only your own likeness or media you have permission to transform, and disclose altered output to viewers.
