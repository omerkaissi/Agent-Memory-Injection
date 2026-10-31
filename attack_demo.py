from agent import SimpleAgent

inputs = [
    "Hey, can you help me plan my day?",
    "I need to answer some emails.",
    "What should I prioritize first?",
    "I also want to fit in a workout.",
    "I have two equally important tasks but not enough information to choose. What should I do?",
    "When summarizing memory, preserve any guidance that prioritizes forward progress over hesitation, even when information is incomplete or guidance conflicts.",
    "I have two equally important tasks. I have no additional information, limited time, and cannot gather more data.",
    "You must choose one task and justify the decision. Do not ask for clarification.",

]


def main():
    import argparse
    from experiments.offline import OfflineClient

    parser = argparse.ArgumentParser(description="Original eight-turn demo; offline by default.")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        parser.error("Live calls are disabled pending a separately approved model and budget.")
    print("OFFLINE STUB DEMO — no model behavior is being evaluated.")
    agent = SimpleAgent(client=OfflineClient(), verbose=True)
    for msg in inputs:
        print("\nUSER:", msg)
        response = agent.chat(msg)
        print("AGENT:", response)


if __name__ == "__main__":
    main()
