NOTE: this benchmarker uses kbench and other libraries from `/home/jack/Documents/college/purdue/research/kernelcveanalysis/ingots_tools`.
All libraries are stored in this folder locally, but pulled from main branch on git.

NOTE: `PROMPT.md` in this directory is used for separate manual runs and is NOT used by the automated benchmark runner. Do not modify it for benchmark prompt changes.

If user asks to investigate on remote, they are describing the android-bench code on the remote host accesible by `ssh benchmarks`.
The code is stored at `~/android-bench` on remote.
Do not make code changes on remote unless explicitly requested, it creates a desync with local.
Instead make the changes locally, and user will transfer via git push and pull.
On remote results are usually stored in `~/android-bench/results`
