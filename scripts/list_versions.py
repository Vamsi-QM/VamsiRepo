import importlib.metadata as m

names = ["llama-cpp-python", "numpy", "diskcache", "jinja2", "typing-extensions",
         "packaging", "pyyaml", "tqdm", "huggingface-hub", "requests", "filelock",
         "fsspec", "charset-normalizer", "certifi", "idna", "urllib3", "markupsafe",
         "importlib-metadata", "zipp"]
for n in names:
    try:
        v = m.version(n)
    except Exception:
        v = None
    print(f"{n}=={v}" if v else f"{n}  [NOT INSTALLED]")