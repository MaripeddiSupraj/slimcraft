# AI Platform — Cheap Open-Source LLM Subscription (India-focused)

## Vision
One subscription, unlimited access to best open-source models. ChatGPT-quality UI, fraction of the cost. Targeted at Indian students and job seekers.

## Target Audience
- **Students** — classroom notes, PDF summarization, homework help, document generation, video explanation
- **Govt job seekers** — aptitude, GK, reasoning practice, mock tests
- **Freelancers/devs** — code generation, email drafting, Slack/GitHub integration

## Core Features

### AI Engine
- Open-source models only (Llama 3, Qwen 2.5, Mistral, DeepSeek, Phi, etc.)
- Image generation via open models (Stable Diffusion, FLUX, etc.)
- Limited bundled tokens for ChatGPT/Gemini (optional upsell)
- Run on cheap GPU: spot instances, RunPod, Vast.ai, Lambda
- Scale to zero when idle

### Platform
- UI on par with ChatGPT/Gemini — conversations, threads, history, search
- Strong auth with session caching (JWT + Redis)
- File upload: PDF, DOCX, images — extract text, summarize
- Export: download chats as PDF/DOCX/TXT, email reports
- Plugins: GitHub PR review, Slack bot, Email drafts, Gmail integration

### Subscription (Monthly)
| Tier | Price | What you get |
|---|---|---|
| Student | ₹99 / $1 | Open models, basic chat, PDF upload, 5 exports/mo |
| Pro | ₹299 / $3.50 | All models, image gen, GitHub/Slack plugins, unlimited exports |
| Pro+ | ₹599 / $7 | Priority queue, ChatGPT/Gemini tokens included, API access |

### Technical Stack
- Frontend: Next.js (chat UI like ChatGPT)
- Backend: FastAPI / Python
- Auth: JWT + Redis session cache
- Model serving: vLLM + Ollama on spot GPU
- Queue: Redis + Celery for background jobs (export, email)
- Database: PostgreSQL + S3 for file storage

## Architecture
```
User → Next.js (CDN) → FastAPI → Auth (JWT/Redis)
                                  → Chat → vLLM/Ollama on spot GPU
                                  → Image → Stable Diffusion / FLUX
                                  → Plugins → GitHub API / Slack API / SMTP
                                  → Export → Celery → PDF/DOCX → Email
```

## Phases
1. Auth + Chat UI (ChatGPT clone with open models)
2. PDF/file upload + summarization
3. Image generation
4. Export + email
5. Plugins (GitHub, Slack, Email)
6. Admin dashboard + analytics
7. ChatGPT/Gemini token bundling
