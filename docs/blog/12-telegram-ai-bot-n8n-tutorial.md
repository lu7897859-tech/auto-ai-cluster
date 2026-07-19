# 12 — Building a Telegram AI Bot Agent with n8n on Your 2C4G VPS

> **Published:** 2026-07-19  
> **Tags:** n8n, Telegram, Bot, 2C4G, Tutorial, AI Agent  
> **Read time:** 12 min

## Why a Telegram Bot?

A Telegram bot is the cheapest, most practical interface for your AI cluster. No web UI to build. No mobile app to maintain. Your users type a message → your n8n workflow calls DeepSeek/OpenAI → the bot replies with AI-generated content.

On a 2C4G VPS, this whole stack runs at **~33 MB RAM overhead** beyond the base cluster. This tutorial walks through every step.

## Architecture

```
Telegram User ──message──▶ Bot API ──webhook──▶ n8n Webhook Node
                                                    │
                                          ┌─────────▼─────────┐
                                          │  AI Gateway (port  │
                                          │  3456)             │
                                          └─────────┬─────────┘
                                                    │
                                          ┌─────────▼─────────┐
                                          │  DeepSeek / OpenAI │
                                          └───────────────────┘
                                                    │
                                          ┌─────────▼─────────┐
                                          │  n8n Respond Node  │
                                          └───────────────────┘
                                                    │
Telegram User ◀──reply── Bot API ◀──webhook response──┘
```

## Step 1: Create the Telegram Bot

Talk to [@BotFather](https://t.me/BotFather) on Telegram:

```
/newbot
Name: My AI Assistant
Username: my_ai_assistant_bot
```

Save the token: `7654321:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`

Then disable privacy mode:

```
/setprivacy → Disable
```

## Step 2: Configure the Webhook

You need a public HTTPS endpoint. Use Cloudflare Tunnel (free) or ngrok.

**Cloudflare Tunnel:**

```bash
cloudflared tunnel create my-ai-bot
cloudflared tunnel route dns my-ai-bot bot.yourdomain.com
```

**ngrok (testing only):**

```bash
ngrok http 5678  # n8n default port
```

Set the webhook URL:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-tunnel.ngrok.io/webhook/telegram"}'
```

Verify:

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

## Step 3: Build the n8n Workflow

### 3a. Webhook Node (Trigger)

| Setting | Value |
|---------|-------|
| HTTP Method | POST |
| Path | `telegram` |
| Response Mode | Last Node |
| Options: Raw Body | true |

### 3b. Code Node — Extract Message

```javascript
const body = $input.first().json;
const chatId = body.message?.chat?.id;
const text = body.message?.text || '';
const userId = body.message?.from?.id;
const username = body.message?.from?.username || 'unknown';

return [{ json: { chatId, text, userId, username } }];
```

### 3c. HTTP Request Node — Call AI

Call your AI gateway or DeepSeek directly:

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://ai-gateway:3456/v1/chat` |
| Body | `{"messages": [{"role": "user", "content": "{{ $json.text }}"}]}` |

### 3d. Code Node — Format Reply

```javascript
const response = $input.first().json;
let replyText = response.choices?.[0]?.message?.content
  || response.content
  || JSON.stringify(response).substring(0, 4000);
if (replyText.length > 4000) replyText = replyText.substring(0, 3997) + '...';

return [{ json: { chatId: $json.chatId, text: replyText } }];
```

### 3e. Respond to Webhook Node

```
method: sendMessage
chat_id: {{ $json.chatId }}
text: {{ $json.text }}
```

## Step 4: Add Conversation Memory

Add a Code Node before the AI call:

```javascript
const memory = {};
const userId = $json.userId;
const text = $json.text;

if (!memory[userId]) memory[userId] = [];
memory[userId].push({ role: 'user', content: text });
if (memory[userId].length > 10) memory[userId] = memory[userId].slice(-10);

const messages = [
  { role: 'system', content: 'You are a helpful AI assistant on a 2C4G VPS.' }
].concat(memory[userId]);

return [{ json: { messages } }];
```

> **Note:** This resets on n8n restart. For production, store in PostgreSQL.

## Resource Usage on 2C4G

| Component | RAM | Notes |
|-----------|:---:|-------|
| Cloudflare Tunnel | ~25 MB | Only needed without public IP |
| Workflow overhead | ~8 MB | Per-call allocation |
| **Total additional** | **~33 MB** | Negligible |

## Production Checklist

- [ ] **Rate limiting** – max 10 messages/user/minute via n8n throttle
- [ ] **User allowlist** – check userId in a Code Node
- [ ] **Command routing** – `/help`, `/status`, `/clear` with a Switch Node
- [ ] **Error messages** – catch API failures, reply "Busy, try again"
- [ ] **Group chat** – check `body.message.chat.type`
- [ ] **Markdown sanitization** – wrap in try-catch, fall back to plain text

## Commands to Implement

```
/help    → "I'm your AI assistant. Send any message and I'll reply."
/status  → "Cluster healthy. Uptime: 12d. API: DeepSeek (OK)"
/clear   → "Memory cleared."
/price   → "Current cost: ~$0.0005 per query via DeepSeek"
```

## Why This Works on 2C4G

Telegram bots are **webhook-driven, not polling**. n8n only allocates memory when a message arrives. Between messages, the workflow sits idle at zero cost. The same $5/month VPS that runs n8n, PostgreSQL, and your AI gateway now runs a full-featured Telegram AI bot.

## Next Steps

1. Add **image generation** – route prompts to Stable Diffusion or DALL-E
2. Add **voice messages** – Whisper speech-to-text
3. Add **scheduled broadcasts** – n8n cron node for daily summaries
4. Turn it into a **multi-agent system** – separate bots for research, coding, writing

---

*Part of the Auto-AI-Cluster series. Published 2026-07-19. [Source on GitHub.](https://github.com/lu7897859-tech/auto-ai-cluster)*
