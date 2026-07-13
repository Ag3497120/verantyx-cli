"""ClassifyOnlyBrain.generate must raise — router path is classify-only."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from router_classifier import ClassifyOnlyBrain, wrap_for_classify


class _StubBrain:
    vector_intervention = False

    def encode(self, *a, **k):
        return None

    def generate(self, *a, **k):
        return [1, 2, 3]


def test_classify_only_generate_raises():
    clf = wrap_for_classify(_StubBrain())
    assert isinstance(clf, ClassifyOnlyBrain)
    try:
        clf.generate([1, 2, 3], 8)
        raise AssertionError("ClassifyOnlyBrain.generate should have raised")
    except RuntimeError as e:
        assert "must not generate" in str(e)


def test_double_wrap_idempotent():
    inner = wrap_for_classify(_StubBrain())
    outer = wrap_for_classify(inner)
    assert outer.underlying is inner.underlying


if __name__ == "__main__":
    test_classify_only_generate_raises()
    test_double_wrap_idempotent()
    print("OK: ClassifyOnlyBrain.generate raises")
