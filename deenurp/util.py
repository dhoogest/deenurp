"""
Utility functions
"""

import contextlib
import functools
import os.path
import shutil
import tempfile

from Bio import SeqIO

class SingletonDefaultDict(dict):
    """
    Dictionary-like object that returns the same value, regardless of key
    """
    def __init__(self, val=None):
        self.val = val

    def __getitem__(self, key):
        return self.val

def memoize(fn):
    cache = {}
    @functools.wraps(fn)
    def inner(*args):
        try:
            return cache[args]
        except KeyError:
            result = fn(*args)
            cache[args] = result
            return result
    return inner

def unique(iterable, key=lambda x: x):
    """
    Choose unique elements from iterable, using the value returned by `key` to
    determine uniqueness.
    """
    s = set()
    for i in iterable:
        k = key(i)
        if k not in s:
            s.add(k)
            yield i

@contextlib.contextmanager
def nothing(obj=None):
    """
    The least interesting context manager.
    """
    yield obj

@contextlib.contextmanager
def ntf(**kwargs):
    """
    Near-clone of tempfile.NamedTemporaryFile, but the file is deleted when the
    context manager exits, rather than when it's closed.
    """
    kwargs['delete'] = False
    tf = tempfile.NamedTemporaryFile(**kwargs)
    try:
        with tf:
            yield tf
    finally:
        os.unlink(tf.name)

@contextlib.contextmanager
def tempcopy(path, **kwargs):
    """
    Create a temporary copy of ``path``, available for the duration of the
    context manager
    """
    prefix, suffix = os.path.splitext(os.path.basename(path))
    a = {'prefix': prefix, 'suffix': suffix}
    a.update(kwargs)
    with open(path) as fp, ntf(**a) as tf:
        shutil.copyfileobj(fp, tf)
        tf.close()
        yield tf.name

@contextlib.contextmanager
def tempdir(**kwargs):
    """
    Create a temporary directory for the duration of the context manager,
    removing on exit.
    """
    td = tempfile.mkdtemp(**kwargs)
    def p(*args):
        return os.path.join(td, *args)
    try:
        yield p
    finally:
        shutil.rmtree(td)

@contextlib.contextmanager
def as_fasta(sequences, **kwargs):
    """
    Write sequences to a temporary FASTA file. returns the name
    """
    if 'suffix' not in kwargs:
        kwargs['suffix'] = '.fasta'
    with ntf(**kwargs) as tf:
        SeqIO.write(sequences, tf, 'fasta')
        tf.flush()
        tf.close()
        yield tf.name

@contextlib.contextmanager
def maybe_tempfile(obj=None, **kwargs):
    """
    Returns a tempfile for the duration of the contextmanager if obj is not
    provided, otherwise returns obj.
    """
    if obj is not None:
        yield obj
    else:
        with ntf(**kwargs) as tf:
            yield tf