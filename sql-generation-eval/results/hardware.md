# Hardware observed during setup

- System RAM: approximately 15.7 GiB reported by Windows.
- GPU: NVIDIA GeForce RTX 3050 6GB Laptop GPU.
- GPU memory: 6144 MiB reported by nvidia-smi.
- Python: 3.11.9.
- SQLite: 3.45.1.
- Operating system: Windows.

Ollama was not found on PATH at initial inspection. No model benchmark has been run.
An installation attempt on 2026-09-15 encountered package-manager download timeouts;
a direct download progressed too slowly to complete within its transfer timeout.
The download processes were stopped, and runtime installation remains pending.
The 7B Q4_K_M artifact is roughly 4.7 GB on disk; GPU residency also depends on the
context cache and runtime buffers. Confirm actual GPU/CPU allocation during the pilot.
Each actual run will capture runtime version, exact model identifiers and hardware state.
