"""Anchor one frozen authoring label without changing its final provenance."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from unittest.mock import patch


def bind_portable_sources(original, root):
    """Keep the original temporal example's normalization independent of cwd.

    The frozen helper emits this one relative label before the unchanged example
    resolves it against its repository. Supply the actual source path at source
    construction; the example itself restores the original logical label. Other
    labels, all source fields, original bodies and the process cwd stay intact.
    """
    temporal = str(Path(root).resolve() / 'examples/temporal_pipeline.py')

    @wraps(original)
    @contextmanager
    def portable_sources():
        import biocompiler.frontend.graph as graph
        source_location = graph.SourceLocation

        def anchored(file, line, function):
            if file == 'examples/temporal_pipeline.py':
                file = temporal
            return source_location(file, line, function)

        # The original helper remains responsible for observing/normalizing the
        # actual source filename and rejecting foreign absolute source paths.
        with patch.object(graph, 'SourceLocation', anchored), original():
            yield

    return portable_sources
