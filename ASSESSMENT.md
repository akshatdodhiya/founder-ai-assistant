# 48-Hour Take-Home Assignment: Founder AI Assistant

## Overview

Build a personal AI assistant for a startup founder.

The founder has information spread across tools like Gmail, Google Calendar, Linear, Slack, Notion, Google Drive, GitHub, or a CRM.

The goal is to build a small but realistic assistant that helps the founder understand what is happening across their work life.

This should not just be a chatbot that calls APIs live. We want you to build a simple context engine that ingests information from different sources, stores it centrally, and retrieves relevant context when answering questions.

## Time Limit

You have 48 hours.

We are not expecting a polished production app. We care more about thoughtful system design, product thinking, and your ability to build a useful prototype quickly.

## What You Need to Build

Build an assistant that:

- Connects to at least 2 data sources
- Stores the data in a central context layer
- Normalizes the data into a shared format
- Lets a founder ask questions across that context
- Retrieves relevant context before answering

You may build any interface you want. This could be a CLI, web app, chat interface, bot, API endpoint, desktop app, or any other interface that makes sense.

The interface does not need to be polished. It just needs to let us interact with the assistant and test the example founder questions.

Real integrations are great, but they are not required. You may use mock data if setting up real integrations takes too long, as long as the architecture is realistic.

To make integrations easier, you may look at tools like Nango, Composio, or Pipedream. These are optional.

We will provide you with an OpenRouter API key that you can use for LLM calls. You are free to use another provider if you prefer, but OpenRouter will be available to you.

## Example Founder Questions

Your assistant should be able to answer realistic questions such as:

- What should I focus on today?
- What should I know before my next meeting?
- What follow-ups am I missing?
- Which tasks are blocked?
- Summarize investor-related activity this week.
- What happened across the company this week?
- Which emails relate to upcoming meetings?
- What customer issues are showing up repeatedly?
- What decisions were made recently?

You should include at least 3 example questions in your final submission.

## Required: Submit a Traces Link

As part of your final submission, you must include a Traces link from traces.com.

This is not part of the founder assistant itself. You do not need to integrate Traces into your app.

Traces is used so we can evaluate your AI-assisted development process, including your prompts, outputs, debugging process, and iteration history.

Please make sure your Traces link is viewable by reviewers.

Before submitting, remove or redact any private API keys, credentials, tokens, or personal data.

## Deliverables

Please submit:

- GitHub repo
- README
- Traces link showing your AI-assisted development workflow
- List of connected data sources
- At least 3 example questions we can test
- Notes on tradeoffs and future improvements

You do not need to submit a demo video.

Instead, we will have a quick 15-minute chat where you walk us through what you built, how it works, and the decisions you made.

## Evaluation Criteria

You will be evaluated on:

### 1. Product Thinking

Does the assistant solve a real founder problem?

We are looking for workflows like daily priorities, meeting prep, follow-up detection, task prioritization, decision summaries, and cross-source context.

### 2. Context Engine

This is the most important part.

We will evaluate how you ingest, normalize, store, and retrieve context. We will also look at whether your assistant is grounded in stored context rather than only relying on live tool calls.

### 3. Engineering Quality

We will evaluate whether the project is easy to run, readable, understandable, and reasonably structured.

### 4. AI Usage and Prompting

We will evaluate how well you use the LLM, how clearly your prompts are structured, whether retrieved context is used well, and whether the assistant avoids hallucinating.

Your Traces submission will help us evaluate this.

### 5. Communication

In the 15-minute chat, we will evaluate whether you can clearly explain your architecture, tradeoffs, decisions, and future improvements.

## Final Reminder

Use the 48 hours wisely.

We are not looking for perfection. We are looking for a thoughtful prototype that shows how you think about product, context, AI systems, engineering tradeoffs, and prompting.

We will also look at the prompts you used during development through your Traces submission, so make sure your workflow shows how you reasoned, iterated, and improved the system.
