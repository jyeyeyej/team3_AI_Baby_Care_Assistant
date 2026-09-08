"""Select at most three relevant memories without exposing unrelated context."""

def select_memories(memories, question: str):
    terms = set(question.lower().split())
    ranked = sorted(memories, key=lambda item: len(terms & set(item.content.lower().split())), reverse=True)
    return ranked[:3]
