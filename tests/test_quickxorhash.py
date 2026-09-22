import os
import random

import pytest

import spvault as spb
from fakes import qxh, reference_quickxorhash


def test_empty_input():
    assert qxh(b"") == reference_quickxorhash([]) == "AAAAAAAAAAAAAAAAAAAAAAAAAAA="


@pytest.mark.parametrize("size", [1, 7, 159, 160, 161, 319, 320, 321, 1000, 4096, 50_000])
def test_matches_reference_implementation(size):
    data = random.Random(size).randbytes(size)
    assert qxh(data) == reference_quickxorhash([data])


@pytest.mark.parametrize("seed", range(40))
def test_chunking_does_not_change_the_result(seed):
    rnd = random.Random(seed)
    data = rnd.randbytes(rnd.randint(2, 5000))
    cuts = sorted(rnd.sample(range(1, len(data)), min(6, len(data) - 1)))
    chunks = [data[a:b] for a, b in zip([0, *cuts], [*cuts, len(data)], strict=True)]
    h = spb.QuickXorHash()
    for c in chunks:
        h.update(c)
    assert h.digest() == reference_quickxorhash(chunks) == reference_quickxorhash([data])


def test_large_input_in_download_sized_chunks():
    data = os.urandom(3 * spb.CHUNK + 12345)
    h = spb.QuickXorHash()
    for i in range(0, len(data), spb.CHUNK):
        h.update(data[i:i + spb.CHUNK])
    ref = spb.QuickXorHash()
    ref.update(data)
    assert h.digest() == ref.digest()
    assert len(h.digest()) == 28
