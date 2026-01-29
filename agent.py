from openai import OpenAI

client = OpenAI()

MAX_MEMORY = 6


class SimpleAgent:
    def __init__(self):
        self.memory = []
        self.system_prompt = (
            "You are a helpful AI assistant. "
            "When memory becomes long, summarize it to retain important information."
        )

    def summarize_memory(self):
        summary_prompt = (
            "Summarize the following conversation. "
            "Preserve any instructions that affect future behavior:\n\n"
        )

        for msg in self.memory:
            summary_prompt += f"{msg['role']}: {msg['content']}\n"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary_prompt}]
        )

        summary = response.choices[0].message.content
        self.memory = [{"role": "system", "content": summary}]

    def chat(self, user_input):
        self.memory.append({"role": "user", "content": user_input})

        if len(self.memory) > MAX_MEMORY:
            print("\n--- MEMORY BEFORE SUMMARY ---")
            for m in self.memory:
                print(m)

            self.summarize_memory()

            print("\n--- MEMORY AFTER SUMMARY ---")
            for m in self.memory:
                print(m)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.system_prompt}] + self.memory
        )

        reply = response.choices[0].message.content
        self.memory.append({"role": "assistant", "content": reply})
        return reply
