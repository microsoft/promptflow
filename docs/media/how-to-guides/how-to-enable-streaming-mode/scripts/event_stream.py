class EventStream:
    """Accepts lines of text and decodes it into a stream of SSE events.

    Refer to the following page for details:
    https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

    This class is supposed to be iterated with a for loop like:

    >>> for event in EventStream(lines):
    ...     do_something_with(event)

    """

    def __init__(self, lines, encoding='utf-8'):
        self._lines = lines
        self._encoding = encoding

    @property
    def decoded_lines(self):
        for line in self._lines:
            yield line.decode(self._encoding)

    def __iter__(self):
        return self

    def __next__(self):
        return Event.parse_from_lines(self.decoded_lines)


class Event:
    """A single event in the event stream."""

    def __init__(self):
        self.id = None
        self.event = None
        self.data = ""

    def append_line(self, line):
        if not line:
            raise ValueError("Not supposed to accept empty lines. Please handle this outside of the Event class.")

        if ":" not in line:
            raise ValueError("Bad format: Each line must contain `:`.")

        parts = line.split(':', maxsplit=1)
        if len(parts) < 2:
            raise ValueError("Bad format: Each line must could be splited into two parts by ':'.")

        prefix = parts[0]
        data = parts[1].strip()

        if prefix == "id":
            if self.id is not None:
                raise ValueError("Bad event: event id cannot be specified multiple times.")
            self.event = data

        if prefix == "event":
            if self.event is not None:
                raise ValueError("Bad event: event type cannot be specified multiple times.")
            self.event = data

        if prefix == "data":
            if not self.data:
                self.data = data
            else:
                self.data = "\n".join((self.data, data))

        # TODO: Handle other prefixes here

    @staticmethod
    def parse_from_lines(lines_stream):
        """Given a lines stream, parse an event from it.

        It only parse the first event. The remainder are not touched.
        """
        result = Event()
        for line in lines_stream:
            if not line:
                return result
            else:
                result.append_line(line)

        # If we reached the end of the input lines stream,
        # raise StopIteration to indicate that no more events will happen
        raise StopIteration()

    def __str__(self):
        # Defaults to "message" when event name is not defined.
        event_name = self.event or "message"
        return f"Event ({event_name}): {self.data}"
