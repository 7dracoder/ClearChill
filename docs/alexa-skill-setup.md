# Alexa Skill Setup Guide

This guide covers setting up the Fridge Observer Alexa skill so you can ask your Echo Dot "what's in my fridge?"

---

## Prerequisites

- Amazon Developer account (free) at [developer.amazon.com](https://developer.amazon.com)
- Echo Dot registered to the same Amazon account
- Fridge Observer running on your Raspberry Pi
- A way to expose your Pi to the internet (ngrok or port forwarding)

---

## 1. Expose the Pi to the Internet

The Alexa Skills Kit needs to reach your Pi's `/alexa` endpoint from the internet.

### Option A: ngrok (easiest for testing)

```bash
# Install ngrok on the Pi
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Authenticate (get token from ngrok.com)
ngrok config add-authtoken <your-token>

# Start tunnel
ngrok http 80
```

Copy the `https://xxxx.ngrok.io` URL — this is your skill endpoint.

### Option B: Port forwarding (permanent)

Forward port 443 on your router to port 80 on the Pi. Use a free DDNS service (e.g. DuckDNS) for a stable hostname.

---

## 2. Create the Alexa Skill

1. Go to [developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask)
2. Click **Create Skill**
3. Name: `Fridge Observer`
4. Model: **Custom**
5. Hosting: **Provision your own**
6. Click **Create skill**

---

## 3. Configure the Interaction Model

In the skill builder, go to **Interaction Model → JSON Editor** and paste:

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "fridge observer",
      "intents": [
        {
          "name": "InventoryQueryIntent",
          "slots": [],
          "samples": [
            "what's in my fridge",
            "what do I have",
            "check my fridge",
            "what food do I have",
            "what's expiring soon",
            "fridge inventory"
          ]
        },
        { "name": "AMAZON.HelpIntent", "samples": [] },
        { "name": "AMAZON.CancelIntent", "samples": [] },
        { "name": "AMAZON.StopIntent", "samples": [] }
      ]
    }
  }
}
```

Click **Save Model** then **Build Model**.

---

## 4. Set the Endpoint

1. Go to **Endpoint** in the left sidebar
2. Select **HTTPS**
3. Default Region URL: `https://your-ngrok-url.ngrok.io/alexa`
4. SSL Certificate: **My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority**
5. Click **Save Endpoints**

---

## 5. Start the Alexa Service on the Pi

```bash
sudo systemctl start fridge-alexa
sudo systemctl enable fridge-alexa
```

---

## 6. Test the Skill

In the Alexa Developer Console, go to **Test** tab, enable testing, and type:

```
ask fridge observer what's in my fridge
```

Or say to your Echo Dot:

> "Alexa, ask fridge observer what's in my fridge"

---

## Supported Voice Commands

| You say | Response |
|---|---|
| "Alexa, ask fridge observer what's in my fridge" | Spoken inventory summary, expiring items first |
| "Alexa, ask fridge observer what's expiring soon" | Items within your spoilage threshold |
| "Alexa, open fridge observer" | Welcome message with help |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Skill not responding | Check ngrok is running and the URL in the endpoint matches |
| "There was a problem" | Check `sudo journalctl -u fridge-alexa` for errors |
| Empty inventory response | Make sure items are in the database — add some via the web app first |
