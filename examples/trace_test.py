import asyncio
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Service name is required for most backends,
# and although it's not necessary for console export,
# it's good to set service name anyways.
resource = Resource(attributes={SERVICE_NAME: "your-service-name"})

traceProvider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(ConsoleSpanExporter())
traceProvider.add_span_processor(processor)
trace.set_tracer_provider(traceProvider)

reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
meterProvider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meterProvider)
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
        await task2
        await task1
        await wait_task("task3", 3)


def sync_task(name: str, wait_seconds: int = 1):
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("wait_seconds", wait_seconds)
        import time

        time.sleep(wait_seconds)
        print(f"Task {name} finished")


def sync_main():
    with tracer.start_as_current_span("sync_main") as span:
        span.set_attribute("attribute", "value")
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit tasks to the executor
            future1 = executor.submit(sync_task, "sync_task1")
            _ = future1
        sync_task("sync_task2", 2)


if __name__ == "__main__":
    #  asyncio.run(main())
    sync_main()
