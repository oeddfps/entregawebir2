"""Optional, version-keyed local reference-vector cache; no remote requests."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def reference_vectors(model, anchors, model_name, revision):
    import numpy as np
    digest = hashlib.sha256(json.dumps([model_name, revision, anchors], ensure_ascii=False).encode()).hexdigest()
    folder = Path(os.getenv('CLEAN_PROCESS_CACHE', str(Path.home() / '.cache' / 'clean_process')))
    path = folder / f'e5-anchors-{digest}.npy'
    try:
        vectors = np.load(path, allow_pickle=False)
        getter = getattr(model, 'get_embedding_dimension', None) or getattr(model, 'get_sentence_embedding_dimension', None)
        dimension = getter() if getter else None
        if vectors.ndim == 2 and vectors.shape[0] == len(anchors) and (dimension is None or vectors.shape[1] == dimension) and np.isfinite(vectors).all():
            return vectors, True
    except (OSError, ValueError, TypeError):
        pass
    vectors = model.encode(anchors, normalize_embeddings=True, show_progress_bar=False, batch_size=16)
    temporary = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            np.save(stream, vectors, allow_pickle=False)
        os.replace(temporary, path)
    except OSError:
        # A read-only cache must not disable local model recognition.
        pass
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
    return vectors, False
