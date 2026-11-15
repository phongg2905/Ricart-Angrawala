from dataclasses import dataclass


@dataclass
class LamportClock:
    value: int = 0

    def tick(self) -> int:
        self.value += 1
        return self.value

    def receive(self, timestamp: int) -> int:
        self.value = max(self.value, timestamp) + 1
        return self.value
