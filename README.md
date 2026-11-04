# Operating system laboratory

Course notes and Python demonstrations for CPU scheduling, synchronization and deadlock handling.

The six CPU scheduling algorithms now use one validated simulator in [`scheduling.py`](scheduling.py). The existing 19 scheduling script paths and seven scheduling notebooks call that shared implementation, so fixes do not need to be repeated across copies.

## Run a scheduling simulation

Python 3.12+ is sufficient; the scheduling simulator has no third-party dependencies.

```sh
python scheduling.py rr
python scheduling.py fcfs
python scheduling.py sjf
python scheduling.py srt
python scheduling.py priority
python scheduling.py priority-preemptive

# Existing entry paths still work:
python Final/rr.py
python "Mahbub Sir/4 Round Robin.py"
```

All CLI entry points now use the same prompt order: process count, each process’s arrival and burst, priority where applicable, then Round Robin quantum. IDs are assigned `P1`, `P2`, etc. The program prints completion, turnaround, waiting and first-response times, averages, CPU utilization from time zero, and a trace that includes idle intervals.

| Algorithm | Rule |
| --- | --- |
| FCFS | Earliest arrival, non-preemptive |
| SJF | Shortest burst among ready processes, non-preemptive |
| SRT | Shortest remaining time, reevaluated on arrivals |
| Round Robin | FIFO ready queue, at most one quantum per turn |
| Priority | Larger numeric priority first, non-preemptive |
| Preemptive priority | Larger numeric priority first, reevaluated on arrivals |

Equal choices use arrival time, then original input order. In Round Robin, processes arriving during or exactly at the end of a quantum enter the queue before the just-expired process is requeued. No context-switch cost, I/O blocking or priority aging is simulated.

## Input and termination guarantees

- Process count: **1–1,000**, with unique nonempty IDs for the programmatic API.
- Arrivals: nonnegative. Bursts and Round Robin quantum: strictly positive.
- Times: at most six decimal places, up to `1e9`. Internal integer micro-units avoid floating-point subtraction stalls. NaN, infinity and unrepresentable tiny times are rejected.
- Priorities: integers in `-1e9..1e9`; larger means higher priority.
- Round Robin rejects workloads whose estimated trace would exceed **200,000 slices**, before simulation starts. Increase the quantum or reduce the workload.
- Invalid input exits with a readable error and nonzero status. Zero quantum and zero processes cannot enter a nonterminating simulation or divide by zero.

Preemptive algorithms advance to the next arrival or completion rather than decrementing by one time unit, so fractional bursts finish correctly. Idle periods jump directly to the next arrival, and ready processes never wait merely because a later process has not arrived yet.

## Use from Python

```python
from scheduling import Process, schedule, print_result

workload = [Process("A", 0, 4), Process("B", 2, 1)]
result = schedule(workload, "rr", quantum=2)
print_result(result)
# Trace: A 0–2, B 2–3, A 3–5
```

Results use `Decimal` times. The input list and immutable `Process` objects are not mutated, and repeated calls do not share state. The old copy-specific, mutating class/function APIs have been replaced by this API; compatibility script filenames remain entry points only.

The files named `fcfs_concurent.py` and `fcfs_with_concurent_process.py` now refer to the single-CPU FCFS simulation. They do not launch real processes or claim to emulate the host OS scheduler.

## Notebooks

Open a notebook from inside the cloned repository so it can locate the shared simulator:

| Topic | Notebook |
| --- | --- |
| FCFS | [First come, first served](Mahbub%20Sir/first_come_first_serve.ipynb) |
| SJF | [Shortest job first](Mahbub%20Sir/shortest_job_first_non_preemptive.ipynb) |
| SRT | [Shortest remaining time](Mahbub%20Sir/shortest_job_first_preemptive_SRT.ipynb) |
| Round Robin | [Round Robin](Mahbub%20Sir/round_robin.ipynb) |
| Priority | [Non-preemptive priority](Mahbub%20Sir/priority_non_primptive.ipynb) |
| Preemptive priority | [Preemptive priority](Mahbub%20Sir/priority_primptive.ipynb) |

Install Jupyter separately if you want the notebook interface. Notebook code cells run without interactive input; edit their sample workload and rerun.

## Other course material

Synchronization and deadlock classroom examples remain in [`Masud Sir/`](Masud%20Sir/) and the corresponding `Final/` files. They are separate teaching exercises, not part of the validated scheduling engine. Some intentionally demonstrate waiting, concurrency or deadlock; their behavior is not covered by the scheduling tests. Historical scheduling implementations remain in Git history.

| Terminal lab | Notes |
| --- | --- |
| Linux basics | [Basic commands](Mid/1%20Basic%20Linux%20Command.md) |
| C | [Compile and run](Mid/2%20Run%20a%20C%20program%20using%20terminal.md) |
| C++ | [Compile and run](Mid/3%20Run%20a%20C++%20program%20using%20terminal.md) |
| Java | [Compile and run](Mid/4%20Run%20a%20Java%20program%20using%20terminal.md) |

## Verification

```sh
python -m unittest discover -s tests -v
```

Windows/Linux CI checks known traces for all six algorithms, quantum boundaries, fractional preemption, idle gaps, stable ties, invalid inputs, trace budgets, repeated calls, 180 randomized workload/algorithm combinations, every compatibility CLI and executable notebook cells. No real sleeps or system process scheduling are used by the simulator.

[License](LICENSE)
