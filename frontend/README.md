# SAT-SA frontend

The SAT-SA frontend is a React + TypeScript application built with Vite. It
requires explicit backend authentication; bearer tokens are held only in memory
for the current page lifetime.

## Local commands

```bash
npm ci
npm run lint
npm run build
npm run dev
```

`npm run build` performs the TypeScript project build and creates the production
bundle. The backend serves `frontend/dist` when that bundle is present.

This client is a supervisory review interface. It does not grant authorization
on its own; protected API routes enforce authorization in the backend.
