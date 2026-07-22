"""Makes the project root importable so `from src.recommender import ...` works.

pytest adds the directory containing the rootdir conftest.py to sys.path, so the
mere existence of this file is what fixes `from src.recommender import ...` in
the tests. Nothing else is needed here.
"""
