# src/oobabot/utils.py

```python
def format_prompt_with_topic(prompt, topic):
    """
    This function prefixes the given prompt with the current channel topic.
    """
    return f"{topic}: {prompt}"
```