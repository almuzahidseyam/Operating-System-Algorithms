"""Deterministic, bounded single-CPU scheduling simulations; no threads or sleeps."""
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import sys

SCALE = 1_000_000
ALGORITHMS = {"fcfs", "sjf", "srt", "rr", "priority", "priority-preemptive"}
MAX_SLICES = 200000


@dataclass(frozen=True)
class Process:
    pid: str
    arrival: object
    burst: object
    priority: int = 0


def ticks(value, positive=False):
    if isinstance(value, bool):
        raise ValueError("Time must be numeric, not boolean")
    try:
        text = str(value)
        if len(text) > 64:
            raise ValueError("Time value is too long")
        number = Decimal(text)
        if not number.is_finite() or number < (Decimal("0.000001") if positive else 0) or number > 1_000_000_000:
            raise ValueError("Time is outside the supported range")
        scaled = number * SCALE
        if scaled != scaled.to_integral_value():
            raise ValueError("Times require at most six decimal places, within 0..1e9; burst and quantum must be positive")
        return int(scaled)
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Invalid time value") from error


def display(value):
    return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")


def schedule(processes, algorithm="rr", quantum=None):
    if algorithm not in ALGORITHMS:
        raise ValueError("Unknown scheduling algorithm")
    if not isinstance(processes, (list, tuple)) or not 1 <= len(processes) <= 1000:
        raise ValueError("Provide 1..1000 processes")
    records = []
    seen = set()
    for index, process in enumerate(processes):
        if not isinstance(process, Process):
            raise ValueError("Use Process objects")
        if type(process.pid) not in (str, int):
            raise ValueError("Process IDs must be strings or integers")
        pid = str(process.pid)
        if not pid or len(pid) > 64 or any(ord(char) < 32 for char in pid) or pid in seen:
            raise ValueError("Process IDs must be unique, nonempty and at most 64 printable characters")
        if type(process.priority) is not int or not -1_000_000_000 <= process.priority <= 1_000_000_000:
            raise ValueError("Priorities must be integers within -1e9..1e9")
        seen.add(pid)
        arrival, burst = ticks(process.arrival), ticks(process.burst, positive=True)
        records.append({"pid":pid,"arrival":arrival,"burst":burst,"remaining":burst,"priority":process.priority,"order":index})
    quantum_ticks = ticks(quantum, positive=True) if algorithm == "rr" else None
    if algorithm == "rr" and sum((p["burst"]+quantum_ticks-1)//quantum_ticks for p in records)+len(records)>MAX_SLICES:
        raise ValueError("Round Robin trace would exceed 200,000 slices; increase the quantum or reduce the workload")
    pending = sorted(records, key=lambda p:(p["arrival"],p["order"]))
    ready = deque()
    trace = []
    now, cursor, completed = 0, 0, 0

    def admit():
        nonlocal cursor
        while cursor < len(pending) and pending[cursor]["arrival"] <= now:
            ready.append(pending[cursor])
            cursor += 1

    def choice(process):
        primary = process["remaining"] if algorithm in {"sjf","srt"} else -process["priority"] if algorithm.startswith("priority") else process["arrival"]
        return primary, process["arrival"], process["order"]

    while completed < len(records):
        admit()
        if not ready:
            next_arrival = pending[cursor]["arrival"]
            if next_arrival > now:
                trace.append((None, now, next_arrival))
            now = next_arrival
            admit()
        if algorithm == "rr":
            current = ready.popleft()
        else:
            current = min(ready, key=choice)
            ready.remove(current)
        duration = min(current["remaining"], quantum_ticks) if algorithm == "rr" else current["remaining"]
        if algorithm in {"srt","priority-preemptive"} and cursor < len(pending):
            duration = min(duration, pending[cursor]["arrival"]-now)
        current.setdefault("first_start", now)
        start, now = now, now+duration
        if algorithm != "rr" and trace and trace[-1][0] == current["pid"] and trace[-1][2] == start:
            trace[-1] = (current["pid"], trace[-1][1], now)
        else:
            trace.append((current["pid"], start, now))
        current["remaining"] -= duration
        admit()  # Boundary arrivals precede the just-expired Round Robin process.
        if current["remaining"]:
            ready.append(current)
        else:
            current["completion"] = now
            completed += 1
    unit = Decimal(SCALE)
    results = []
    for record in records:
        turnaround = record["completion"]-record["arrival"]
        results.append({"pid":record["pid"],"arrival":Decimal(record["arrival"])/unit,"burst":Decimal(record["burst"])/unit,
                        "completion":Decimal(record["completion"])/unit,"turnaround":Decimal(turnaround)/unit,
                        "waiting":Decimal(turnaround-record["burst"])/unit,"response":Decimal(record["first_start"]-record["arrival"])/unit})
    return {"processes":results,"trace":[(pid,Decimal(start)/unit,Decimal(end)/unit) for pid,start,end in trace],
            "average_waiting":sum(p["waiting"] for p in results)/len(results),
            "average_turnaround":sum(p["turnaround"] for p in results)/len(results),
            "utilization_percent":Decimal(sum(p["burst"] for p in records))*100/Decimal(now)}


def print_result(result):
    print("PID\tArrival\tBurst\tCompletion\tTurnaround\tWaiting\tResponse")
    for process in result["processes"]:
        print("\t".join([process["pid"],*(display(process[field]) for field in ["arrival","burst","completion","turnaround","waiting","response"])]))
    print("Average waiting:", display(result["average_waiting"]))
    print("Average turnaround:", display(result["average_turnaround"]))
    print("CPU utilization from time zero:", display(result["utilization_percent"]), "%")
    print("Execution trace:")
    for pid, start, end in result["trace"]:
        print(f"  {display(start)} -> {display(end)}: {pid if pid is not None else 'IDLE'}")


def main(algorithm=None):
    if algorithm is None:
        if len(sys.argv) != 2 or sys.argv[1] not in ALGORITHMS:
            print("Usage: python scheduling.py {fcfs|sjf|srt|rr|priority|priority-preemptive}", file=sys.stderr)
            return 2
        algorithm = sys.argv[1]
    try:
        count = int(input("Number of processes (1..1000): "))
        if not 1 <= count <= 1000:
            raise ValueError("Process count must be 1..1000")
        processes = []
        for number in range(1,count+1):
            arrival = input(f"P{number} arrival: ")
            burst = input(f"P{number} burst: ")
            ticks(arrival)
            ticks(burst, positive=True)
            priority = int(input(f"P{number} priority (larger runs first): ")) if algorithm.startswith("priority") else 0
            processes.append(Process(f"P{number}",arrival,burst,priority))
        quantum = input("Positive time quantum: ") if algorithm == "rr" else None
        print_result(schedule(processes,algorithm,quantum))
        return 0
    except (ValueError, EOFError) as error:
        print(f"Invalid workload: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
