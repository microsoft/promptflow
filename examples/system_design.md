# Chats about how to design a distributed tracing system


__Q: I have a flow executor service runs as an app and exposes RESTFul API. and then we also has a CLI app which send calls to the executor service via REST. Where do I need to create the trace provider? Should I be done within the flow executor service as it is a separated app?__


---

In distributed tracing, it is essential to create spans and traces at various points in your system to capture the full journey of requests as they traverse through different services and applications. In your case, you have two distinct components: the flow executor service (which runs as an app and exposes a RESTful API) and a CLI app that makes calls to this service.

Here's how you should approach tracing in each component:

### Flow Executor Service

**Tracer Provider Setup**: The flow executor service should have its own `TracerProvider` set up. This is because it's a standalone application that handles incoming RESTful API requests. By setting up a `TracerProvider` in the executor service, you ensure that you can generate spans for operations performed by this service.

When a request hits the executor service, the service should check for incoming tracing information (like trace context headers) from the CLI app. If present, it should use this information to continue the trace. If not, it should start a new trace. This setup allows the executor service to be traced independently of the CLI app, which is useful if other clients besides the CLI app are interacting with the service.

### CLI App

**Tracer Provider Setup**: The CLI app should also have its own `TracerProvider` set up if you want to trace the CLI app's behavior, such as the time it takes to prepare the request, handle the response, or any other processing it might do.

When the CLI app sends a call to the executor service, it should propagate the trace context (e.g., trace ID and span ID) in the HTTP headers. This allows the executor service to link its work as a child span to the span representing the CLI app's request.

### Propagation

**Context Propagation**: To ensure that the trace context is properly propagated from the CLI app to the executor service, you need to use a context propagation mechanism supported by OpenTelemetry. This typically involves using HTTP headers like `traceparent` from the W3C Trace Context specification to carry the trace context over the network.

**Example**: When the CLI app sends an HTTP request to the executor service, it should inject the current trace context into the HTTP headers. The executor service, upon receiving the request, should extract the trace context from the headers and use it to create a new span as a continuation of the trace.

### Summary

In summary, you should create a `TracerProvider` in both the flow executor service and the CLI app if you want to have end-to-end tracing:

- **Flow Executor Service**: Set up a `TracerProvider` to trace the handling of incoming requests and any internal processing. Extract trace context from incoming HTTP headers to continue traces started by clients.

- **CLI App**: Set up a `TracerProvider` to trace the CLI app's operations and outgoing HTTP requests. Inject trace context into HTTP headers when calling the executor service.

By instrumenting both components, you'll have a comprehensive view of the entire transaction from the CLI app's invocation through the execution of the flow in the service, which is valuable for diagnosing issues and understanding system behavior.

---

__Q: Show me detail samples with http header names__


---

Certainly! Below are detailed examples of how you might implement distributed tracing with OpenTelemetry in both a CLI app and a flow executor service. We'll use HTTP headers for context propagation according to the W3C Trace Context specification.

### Flow Executor Service

In the flow executor service, you'll need to set up the `TracerProvider`, create spans for incoming requests, and extract trace context from HTTP headers.

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.propagate import extract
from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware
from flask import Flask, request

# Configure the TracerProvider
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

app = Flask(__name__)

# Add OpenTelemetry middleware to Flask to automatically trace requests
app.wsgi_app = OpenTelemetryMiddleware(app.wsgi_app)

# Define your API endpoint
@app.route("/execute-flow", methods=["POST"])
def execute_flow():
    # Extract trace context from incoming headers
    context = extract(request.headers)

    # Obtain a tracer from the provider
    tracer = tracer_provider.get_tracer(__name__)

    # Create a new span using the extracted context
    with tracer.start_as_current_span("execute-flow-handler", context=context):
        # Perform the flow execution logic
        # ...
        return "Flow executed", 200

if __name__ == "__main__":
    app.run(port=5000)
```

In this example, the `OpenTelemetryMiddleware` automatically handles the extraction of the context from the incoming HTTP headers and creates spans for each incoming request.

### CLI App

In the CLI app, you'll set up the `TracerProvider`, create spans for outgoing HTTP requests, and inject trace context into HTTP headers.

```python
import requests
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.propagate import inject
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure the TracerProvider
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

# Automatically instrument all outgoing requests made using 'requests'
RequestsInstrumentor().instrument()

# Obtain a tracer from the provider
tracer = tracer_provider.get_tracer(__name__)

# Function to execute a flow by calling the executor service
def execute_flow_via_service():
    with tracer.start_as_current_span("cli-execute-flow"):
        # Prepare the request to the executor service
        url = "http://localhost:5000/execute-flow"
        payload = {"data": "example payload"}

        # Propagate the current trace context into the outgoing HTTP headers
        headers = {}
        inject(headers)

        # Send the request to the executor service
        response = requests.post(url, json=payload, headers=headers)
        return response

# CLI logic
if __name__ == "__main__":
    response = execute_flow_via_service()
    print(response.text)
```

In the CLI app example, we use the `RequestsInstrumentor` from the `opentelemetry-instrumentation-requests` package to automatically trace HTTP requests made with the `requests` library. The `inject` function injects the current trace context into the `headers` dictionary, which is then passed along with the HTTP request.

### HTTP Headers for Trace Context Propagation

According to the W3C Trace Context specification, the following HTTP headers are used to propagate trace context:

- `traceparent`: Contains the trace ID, parent span ID, and trace flags


---

__Q: How does the traceparent data look like? I want to view its format in detail__


---

The `traceparent` HTTP header is used to carry the trace context across service boundaries according to the W3C Trace Context specification. The header contains essential information that allows distributed tracing systems to connect spans into a single, coherent trace. The value of the `traceparent` header has the following format:

```
version-trace_id-parent_id-trace_flags
```

Each of the fields in the `traceparent` header is described in detail below:

1. **version**: This is an 8-bit field that represents the version of the `traceparent` header. As of my knowledge cutoff date in 2023, the version is `00`. This is the only officially supported version of the Trace Context specification. The version field is encoded as two hexadecimal digits.

2. **trace_id**: This is a 128-bit field that represents the ID of the entire trace. It is globally unique and encoded as 32 hexadecimal digits. The `trace_id` remains constant as the trace propagates through different services.

3. **parent_id**: This is a 64-bit field that represents the ID of the parent span (the caller). This field is also known as the `span_id` and is encoded as 16 hexadecimal digits. The `parent_id` changes as spans are created within different services, representing the direct parent of the current span.

4. **trace_flags**: This is an 8-bit field that provides additional information about the trace, such as whether the trace is sampled. The trace flags are encoded as two hexadecimal digits. The least significant bit (rightmost bit) of the trace flags is the `sampled` flag, which indicates if the trace is sampled (typically `01` for sampled and `00` for not sampled).

Here's an example of what the `traceparent` header might look like:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

- `00`: The version of the trace context specification.
- `4bf92f3577b34da6a3ce929d0e0e4736`: The trace ID, a 128-bit identifier for the trace.
- `00f067aa0ba902b7`: The parent ID, a 64-bit identifier for the parent span.
- `01`: The trace flags, indicating that the trace is sampled.

The `traceparent` header is used in conjunction with the `tracestate` header in some cases, which can carry additional vendor-specific trace context information. However, the `traceparent` header provides the essential fields required for basic trace context propagation.


---

__Q: The CLI app has some attributes like request_id, user_agent. Will this be propogated to the executor service? Will they set as the attributes or resources to the executor spans?__

---

Attributes like `request_id`, `user_agent`, and other metadata are not automatically propagated through the `traceparent` header for distributed tracing. The `traceparent` header is specifically designed to carry only the essential information required for trace context propagation, such as the `trace_id`, `parent_id`, and `trace_flags`.

If you want to propagate additional information like `request_id` or `user_agent` from the CLI app to the executor service and have them associated with spans in the executor service, you have a couple of options:

1. **Custom Headers**: You can propagate additional information by including custom HTTP headers in your requests. The executor service can extract these headers and set them as span attributes.

   **CLI App**:
   ```python
   headers = {}
   inject(headers)  # Inject trace context
   headers['X-Request-ID'] = "12345"  # Custom header for request_id
   headers['User-Agent'] = "CLI Tool v1.0"  # Custom header for user_agent

   response = requests.post(url, json=payload, headers=headers)
   ```

   **Executor Service**:
   ```python
   @app.route("/execute-flow", methods=["POST"])
   def execute_flow():
       context = extract(request.headers)
       tracer = trace.get_tracer(__name__)
       with tracer.start_as_current_span("execute-flow-handler", context=context) as span:
           # Set additional attributes from custom headers
           span.set_attribute("request_id", request.headers.get("X-Request-ID"))
           span.set_attribute("user_agent", request.headers.get("User-Agent"))

           # Perform the flow execution logic
           # ...
           return "Flow executed", 200
   ```

2. **Trace Attributes**: OpenTelemetry allows you to set attributes directly on spans. If the additional information is available when the span is started, you can include it as span attributes.

   **Executor Service**:
   ```python
   @app.route("/execute-flow", methods=["POST"])
   def execute_flow():
       context = extract(request.headers)
       tracer = trace.get_tracer(__name__)
       with tracer.start_as_current_span("execute-flow-handler", context=context) as span:
           # Set additional attributes from the request or other sources
           span.set_attribute("request_id", "12345")
           span.set_attribute("user_agent", "CLI Tool v1.0")

           # Perform the flow execution logic
           # ...
           return "Flow executed", 200
   ```

In both cases, the additional information will be set as span attributes, not as resources. In OpenTelemetry, a `Resource` represents the entity producing telemetry and is typically associated with the service or application instance as a whole, rather than with individual spans or requests.

By setting these values as span attributes, you can query, filter, and analyze your trace data based on `request_id`, `user_agent`, or any other custom attributes you've included in your instrumentation.


---

__Q: How to set the exporters? Are the exporters running in the same process as my service?

---

Exporters in OpenTelemetry are components that send the telemetry data (traces, metrics, logs) collected by the SDK to a backend of your choice, such as Jaeger, Zipkin, Prometheus, or a proprietary monitoring service like New Relic or Datadog. The configuration of exporters typically involves specifying the destination for the data and any necessary credentials or configuration required to authenticate with that backend service.

### How to Set Up Exporters

Setting up exporters involves a few steps:

1. **Choose an Exporter**: OpenTelemetry provides a variety of exporters for different backends. Select the exporter that matches your backend service. Some backends might have more than one supported exporter, so choose the one that fits your needs.

2. **Configure the Exporter**: Provide necessary configuration details such as the endpoint to which the data should be sent, authentication tokens, or any other service-specific configuration.

3. **Register the Exporter with the TracerProvider**: Create and register the exporter with the `TracerProvider` so that the collected traces are exported to the desired backend.

Here's a simplified example of setting up an exporter (using the console exporter for demonstration purposes):

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

# Create a TracerProvider
tracer_provider = TracerProvider()

# Configure the ConsoleSpanExporter, which prints the traces to the console
console_exporter = ConsoleSpanExporter()

# Register the exporter with the TracerProvider
tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))

# Assign the configured TracerProvider to the global tracer provider
trace.set_tracer_provider(tracer_provider)
```

### Exporter Processes

Exporters typically run in the same process as your service. They work in the background, collecting and batching telemetry data before sending it to the configured backend. This means they should be lightweight and not significantly impact the performance of your service.

However, in scenarios where you want to offload the work of exporting data from your service processes, you might consider using an OpenTelemetry Collector. The collector is a separate service that receives telemetry data, processes it, and then exports it to one or more backends. In such a setup, your service would use an exporter to send data to the collector (which can be running locally or remotely), and the collector would then manage the final data export.

Here is an example of setting up an exporter to send data to an OpenTelemetry Collector:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Create a TracerProvider
tracer_provider = TracerProvider()

# Configure the OTLP exporter to send data to the OpenTelemetry Collector
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)

# Register the exporter with the TracerProvider using a BatchSpanProcessor
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Assign the configured TracerProvider to the global tracer provider
trace.set_tracer_provider(tracer_provider)
```

In this example, the `OTLPSpanExporter` is used to send data to an OpenTelemetry Collector running at `localhost:4317`.

Remember to tailor the exporter setup to match your specific backend and deployment scenario, ensuring that you handle any necessary security, performance, and reliability considerations.


---

__Q: Thanks a lot. I need to introduce the system design to my boss within 3 minutes. Could you help summarize the conversation above? Listing the key points in bullet points would be better.__

---

Of course! Here's a comprehensive summary of our entire conversation:

1. **System Design Introduction**: You requested assistance in summarizing a system design for your boss, particularly focusing on distributed tracing with OpenTelemetry.

2. **Distributed Tracing Key Points**:
   - The CLI app and flow executor service should each have a `TracerProvider`.
   - The `traceparent` header is used for trace context propagation.
   - The `traceparent` header includes `version`, `trace_id`, `parent_id`, and `trace_flags`.
   - Additional metadata like `request_id` can be sent using custom headers.
   - Span attributes and resources are defined to add context to traces.
   - Trace data is analyzed and visualized in a backend system.

3. **Exporters**:
   - Exporters send telemetry data to backends or an OpenTelemetry Collector.
   - They typically run within the same process as your service.
   - Exporters should be configured to minimize performance impact.

4. **OpenTelemetry Collector**:
   - A separate component that can receive, process, and export telemetry data.
   - Services use an OTLP exporter to send data to the collector.
   - The collector centralizes data processing and can export to multiple backends.
   - Using a collector can offload processing from the service instances.

The overall conversation touched upon the setup and configuration of distributed tracing using OpenTelemetry, the role of exporters and how they function within your service process, and the use of the OpenTelemetry Collector to aggregate and forward telemetry data to backend systems.