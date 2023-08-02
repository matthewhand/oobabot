```python
from src.oobabot.utils import *
from src.oobabot.channel import get_current_channel_topic
from src.oobabot.llm import prefix_prompt_to_llm

def main():
    # Get the current channel topic
    current_topic = get_current_channel_topic()

    # Prefix the prompt to the llm using the current channel topic
    prefix_prompt_to_llm(current_topic)

if __name__ == "__main__":
    main()
```