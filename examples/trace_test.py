import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
# Service name is required for most backends,
# and although it's not necessary for console export,
# it's good to set service name anyways.
resource = Resource(attributes={SERVICE_NAME: "your-service-name"})

traceProvider = TracerProvider(resource=resource)
# traceProvider = get_tracer_provider()
# processor = BatchSpanProcessor(ConsoleSpanExporter())
# traceProvider.add_span_processor(processor)
processor = BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=""))
traceProvider.add_span_processor(processor)
processor = BatchSpanProcessor(jaeger_exporter)
traceProvider.add_span_processor(processor)
trace.set_tracer_provider(traceProvider)

zipkin_exporter = ZipkinExporter(
    # Optional: configure the endpoint
    # endpoint="http://localhost:9411/api/v2/spans",
    # Optional: configure the service name
    # service_name="my-service",
)

tracer_provider = trace.get_tracer_provider()
tracer_provider.add_span_processor(BatchSpanProcessor(zipkin_exporter))

# reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
# meterProvider = MeterProvider(resource=resource, metric_readers=[reader])
# metrics.set_meter_provider(meterProvider)
tracer = trace.get_tracer(__name__)


async def wait_task(name: str, wait_seconds: int = 1):
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("wait_seconds", wait_seconds)
        await asyncio.sleep(wait_seconds)
        print(f"Task {name} finished")


async def main():
    with tracer.start_as_current_span("main") as span:
        span.set_attribute("attribute", "value")
        task1 = asyncio.create_task(wait_task("task1", 2))
        task2 = asyncio.create_task(wait_task("task2", 1))
        span.add_event("Start Await", {"name": "value", "my_key": "my_value"})
        await task2
        await task1
        await wait_task("task3", 3)
        span.add_event("End Await", {"name": "value", "my_key": "my_value"})

    first_span_context = span.get_span_context()
    link_to_first_span = trace.Link(first_span_context)

    with tracer.start_as_current_span("linked", links=[link_to_first_span]) as linked:
        linked.set_attribute("my_attribute", "my_value")
        await wait_task("task4", 1)


def sync_task(name: str, wait_seconds: int = 1):
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("wait_seconds", wait_seconds)
        import time

        time.sleep(wait_seconds)
        print(f"Task {name} finished")


def set_context(context: contextvars.Context):
    for var, value in context.items():
        var.set(value)


def sync_main():
    with tracer.start_as_current_span("sync_main") as span:
        span.set_attribute("attribute", "value")
        with ThreadPoolExecutor(
            max_workers=2, initializer=set_context, initargs=(contextvars.copy_context(),)
        ) as executor:
            # Submit tasks to the executor
            executor.submit(sync_task, "sync_task1")
        sync_task("sync_task2", 2)


if __name__ == "__main__":
    asyncio.run(main())
    # sync_main()
