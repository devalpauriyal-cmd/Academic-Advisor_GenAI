# ALICE frontend

Next.js App Router interface for the ALICE academic advisor. The application lives in `app/page.tsx`; its permanent name is defined in `app/identity.ts`.

From this directory:

```sh
npm ci
```

Copy `.env.local.example` to `.env.local` and set `NEXT_PUBLIC_API_URL=http://localhost:8000`. This URL is public browser configuration. Never put provider credentials in `NEXT_PUBLIC_*` variables.

```sh
npm run dev
```

Open http://localhost:3000 with the FastAPI backend running. The API origin must be allowed by `ALLOWED_ORIGINS` in the backend environment. After changing the API URL, restart development or rebuild production.

```sh
npm run lint
npm run build
npm start
```

The production build downloads Geist fonts from Google Fonts and requires network access. Microphone input needs browser permission and a secure context (HTTPS or localhost). Voice transcription and transcript-image extraction need working backend provider keys. Read-aloud uses browser speech synthesis when a suitable voice exists, with cloud TTS as a fallback.

See the [project README](../README.md) for complete setup, architecture, API details and verified limitations.
