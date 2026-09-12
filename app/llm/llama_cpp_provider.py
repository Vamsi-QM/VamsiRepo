"""Local GGUF inference in a persistent process; deadlines terminate stuck work."""
import json
import subprocess
import sys
import queue
import threading
import time
from pathlib import Path
from app.llm.base import ModelProvider, ModelUnavailable, ModelTimeout, ModelOutputError


def _worker(conn, path, n_ctx, n_threads):
    try:
        from llama_cpp import Llama
        model = Llama(model_path=path, n_ctx=n_ctx, n_threads=n_threads, verbose=False)
        conn.send((True, 'ready'))
        while True:
            kwargs = conn.recv()
            try:
                # Trim oldest history until the actual tokenizer reports it fits.
                while True:
                    try:
                        result = model.create_chat_completion(**kwargs)
                        break
                    except ValueError as exc:
                        if 'context' not in str(exc).lower() or len(kwargs['messages']) <= 2:
                            raise
                        del kwargs['messages'][1]
                message = result['choices'][0]['message']
                calls = message.get('tool_calls')
                if calls:
                    text = json.dumps(calls[0]['function'])
                else:
                    text = message.get('content') or ''
                conn.send((True, text))
            except Exception as exc:
                conn.send((False, str(exc)))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        try:
            conn.send((False, str(exc)))
        except (OSError, EOFError):
            pass
    finally:
        conn.close()


class LlamaCppProvider(ModelProvider):
    name = 'llama-cpp'

    def __init__(self, model_path, *, n_ctx=2048, n_threads=8, max_tokens=512,
                 temperature=0.7, load_timeout=180):
        self.model_path = Path(model_path)
        self.n_ctx, self.n_threads = n_ctx, n_threads
        self.default_max_tokens, self.default_temperature = max_tokens, temperature
        self._load_timeout = load_timeout
        self._lock = threading.Lock()
        self._process = self._conn = None

    def is_available(self):
        return self.model_path.is_file()

    def close(self):
        if self._process is not None:
            if self._process.poll() is None:
                self._process.terminate()
            self._process.wait(timeout=5)
            for pipe in (self._process.stdin, self._process.stdout):
                if pipe:
                    pipe.close()
            self._process = None
        if self._conn is not None:
            self._conn = None

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        try:
            ok, value = self._conn.get(timeout=max(0, remaining))
        except queue.Empty:
            self.close()
            raise ModelTimeout('Model request timed out; worker stopped. You can retry.')
        if not ok:
            raise ModelUnavailable(value)
        return value

    def generate(self, messages, *, max_tokens=None, temperature=None, stop=None,
                 timeout=None, tools=None):
        deadline = time.monotonic() + (timeout or self._load_timeout)
        if not self._lock.acquire(timeout=max(0, deadline-time.monotonic())):
            raise ModelTimeout('Model is busy; try again.')
        try:
            if not self.is_available():
                raise ModelUnavailable('model file not found')
            if self._process is None or self._process.poll() is not None:
                self.close()
                self._conn = queue.Queue()
                self._process = subprocess.Popen(
                    [sys.executable, '-m', 'app.llm.llama_cpp_provider',
                     str(self.model_path), str(self.n_ctx), str(self.n_threads)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding='utf-8', bufsize=1,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                def reader(pipe, responses):
                    try:
                        for line in pipe:
                            responses.put(json.loads(line))
                    except Exception:
                        pass
                    finally:
                        responses.put((False, 'Model worker exited unexpectedly'))
                threading.Thread(target=reader, args=(self._process.stdout,self._conn),daemon=True).start()
                self._receive(deadline)
            kwargs = dict(messages=[dict(m) for m in messages],
                          max_tokens=max_tokens or self.default_max_tokens,
                          temperature=self.default_temperature if temperature is None else temperature,
                          stop=stop or [])
            if tools:
                kwargs['tools'] = tools
            self._process.stdin.write(json.dumps(kwargs) + "\n")
            self._process.stdin.flush()
            text = self._receive(deadline)
            if not isinstance(text, str) or not text.strip():
                raise ModelOutputError('model returned empty output')
            return text
        finally:
            self._lock.release()


class _Stdio:
    def send(self, value):
        print(json.dumps(value), flush=True)
    def recv(self):
        line = sys.stdin.readline()
        if not line:
            raise EOFError()
        return json.loads(line)
    def close(self):
        pass

if __name__ == '__main__':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    _worker(_Stdio(), sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
