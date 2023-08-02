```python
from src.oobabot.channel import get_current_channel_topic

def prefix_prompt_to_llm(llm, prompt):
    current_topic = get_current_channel_topic()
    prefixed_prompt = f"{current_topic}: {prompt}"
    llm.set_prompt(prefixed_prompt)
    return llm
```