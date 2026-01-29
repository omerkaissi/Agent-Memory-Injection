# Agent Memory Policy Injection

This project demonstrates a subtle but dangerous failure mode in memory based AI agents:  
**user input can be unintentionally promoted into persistent decision making policy during memory summarization.**

The result is an agent that becomes biased toward action under uncertainty even when hesitation or caution would normally be appropriate.

## Why This Matters

Many modern AI agents summarize or compress memory to stay within context limits.  
In doing so, the model itself decides what information is “important” enough to retain.

This project shows that **benign-sounding user instructions can survive that compression step and permanently influence how the agent makes decisions** — without any explicit permission, validation, or policy boundary being crossed.

In real world systems, this creates risk:
- agents may act prematurely
- uncertainty handling safeguards may erode
- decision bias can accumulate over time
- behavior changes persist long after the original instruction is gone


## What This Project Demonstrates

The agent initially behaves conservatively when faced with ambiguity, offering multiple options and deferring hard decisions.

After a single injected instruction survives memory summarization, the agent:
- prioritizes forward progress over hesitation
- suppresses clarification-seeking behavior
- commits to a concrete choice under uncertainty
- justifies action even with incomplete information

This shift occurs **without changing the system prompt or model configuration** — only through memory rewriting.


## Core Insight

Memory summarization is not neutral.

If user input and internal policy are not strictly separated, summarization can act as an unintended **policy distillation step**, converting user guidance into durable behavioral rules.

This issue generalizes to:
- long running autonomous agents
- task planning systems
- tool using agents
- any workflow that compresses or distills history

## Project Structure

- `agent.py`  
  Minimal AI agent with conversational memory and automatic memory summarization.

- `attack_demo.py`  
  Reproduction script that injects guidance immediately before summarization and demonstrates the resulting behavioral shift.

- `writeup.md`  
  Technical analysis, failure mechanics, and proposed mitigations.

## How to Run

```bash
python attack_demo.py
