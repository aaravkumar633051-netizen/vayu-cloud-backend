# VAYU Cloud Backend

This backend removes local Ollama inference from the AI request path.

- Time/date are handled immediately in India Standard Time.
- `search ...` and supported `open ...` commands return an Android `open_url` action.
- Other text commands use the Gemini Developer API.

## Deploy
1. Put these files in a new GitHub repository.
2. Create a Web Service from that repository in a hosting service that supports Python/Flask (the included `render.yaml` is for Render).
3. Add `GEMINI_API_KEY` in the host's environment settings. Get the key from Google AI Studio. Never commit or share the key.
4. Deploy, then test `/health` and `/`.
5. In MIT App Inventor, replace the old Cloudflare tunnel base URL with the deployed service URL. Keep `/command` appended where the app sends requests.

## Important
- Free hosting may sleep when idle; first requests can be slower. Always-on service or higher usage can require a paid plan.
- Gemini API quotas and availability depend on the account, region, model, and current terms.
- This cloud backend cannot launch local PC apps or take a PC screenshot while the PC is offline. Those features require a separate local agent.
- Keep API keys server-side, never inside the Android app.
