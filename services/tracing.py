from contextlib import contextmanager

try:
    from opentelemetry import trace
except ImportError:
    trace = None


@contextmanager
def traced_span(name, **attributes):
    """OpenTelemetry span when available, otherwise a no-op context."""
    if trace is None:
        yield None
        return

    tracer = trace.get_tracer("frametruth")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span
