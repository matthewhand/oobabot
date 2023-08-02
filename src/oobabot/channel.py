```python
class Channel:
    def __init__(self):
        self.topic = ""

    def set_topic(self, topic):
        self.topic = topic

    def get_current_channel_topic(self):
        return self.topic
```