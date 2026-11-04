import contextlib
from decimal import Decimal
import io
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

from scheduling import ALGORITHMS, Process, schedule

ROOT=Path(__file__).resolve().parents[1]


class SchedulingTests(unittest.TestCase):
    def test_known_completion_times_for_all_six_algorithms(self):
        processes=[Process("P1",0,5,1),Process("P2",1,2,3),Process("P3",2,1,4)]
        expected={"fcfs":[5,7,8],"sjf":[5,8,6],"srt":[8,3,4],"rr":[8,4,5],"priority":[5,8,6],"priority-preemptive":[8,4,3]}
        for algorithm,completion in expected.items():
            with self.subTest(algorithm=algorithm):
                result=schedule(processes,algorithm,2)
                self.assertEqual([p["completion"] for p in result["processes"]],completion)

    def test_round_robin_boundary_arrivals_precede_requeued_process(self):
        result=schedule([Process("A",0,4),Process("B",2,1)],"rr",2)
        self.assertEqual(result["trace"],[("A",0,2),("B",2,3),("A",3,5)])

    def test_fractional_preemption_terminates_exactly(self):
        processes=[Process("A","0","1.5",1),Process("B","0.25","0.5",2)]
        for algorithm in ["srt","priority-preemptive"]:
            result=schedule(processes,algorithm)
            self.assertEqual(result["trace"],[("A",Decimal(0),Decimal(".25")),("B",Decimal(".25"),Decimal(".75")),("A",Decimal(".75"),Decimal(2))])
            self.assertEqual(result["processes"][0]["waiting"],Decimal(".5"))

    def test_idle_gaps_and_utilization(self):
        result=schedule([Process("A",5,1),Process("B",10,2)],"rr",1)
        self.assertEqual(result["trace"],[(None,0,5),("A",5,6),(None,6,10),("B",10,11),("B",11,12)])
        self.assertEqual(result["utilization_percent"],25)
        self.assertEqual(result["average_waiting"],0)

    def test_equal_arrival_ties_preserve_input_order(self):
        for algorithm in ALGORITHMS:
            result=schedule([Process("Z",0,1,1),Process("A",0,1,1)],algorithm,1)
            self.assertEqual(result["trace"][0][0],"Z")

    def test_no_idle_jump_while_an_arrived_process_is_ready(self):
        result=schedule([Process("A",0,3),Process("B",100,1)],"rr",1)
        self.assertEqual(result["processes"][0]["completion"],3)
        self.assertEqual(result["trace"][3],(None,3,100))

    def test_invalid_quantum_and_process_count_are_rejected(self):
        for quantum in [0,-1,float("nan"),float("inf"),True,"0.0000001","1e1000000000"]:
            with self.subTest(quantum=quantum),self.assertRaises(ValueError): schedule([Process("A",0,1)],"rr",quantum)
        for processes in [[],[Process(str(i),0,1) for i in range(1001)]]:
            with self.assertRaises(ValueError): schedule(processes,"rr",1)

    def test_invalid_arrival_burst_ids_priority_and_precision(self):
        for process in [Process("A",-1,1),Process("A",0,0),Process("A",0,-1),Process("A",0,float("nan")),Process("A",True,1),Process("A",0,1,1.5),Process("bad\nID",0,1),Process(None,0,1),Process("A",0,"0.0000001")]:
            with self.assertRaises(ValueError): schedule([process],"fcfs")
        with self.assertRaises(ValueError): schedule([Process("A",0,1),Process("A",1,1)],"fcfs")

    def test_trace_budget_prevents_tiny_quantum_resource_exhaustion(self):
        with self.assertRaisesRegex(ValueError,"200,000"): schedule([Process("A",0,1000000)],"rr",".000001")

    def test_inputs_are_immutable_and_calls_have_no_shared_state(self):
        processes=[Process("B",2,1),Process("A",0,2)]
        original=list(processes)
        first=schedule(processes,"fcfs")
        self.assertEqual(processes,original)
        self.assertEqual(first,schedule(processes,"fcfs"))

    def test_random_workloads_conserve_burst_and_time_metrics(self):
        rng=random.Random(42)
        for _ in range(30):
            processes=[Process(str(i),rng.randrange(8),rng.randrange(1,8),rng.randrange(4)) for i in range(5)]
            for algorithm in ALGORITHMS:
                result=schedule(processes,algorithm,2)
                last=0
                executed={p.pid:0 for p in processes}
                for pid,start,end in result["trace"]:
                    self.assertEqual(start,last)
                    self.assertGreater(end,start)
                    last=end
                    if pid is not None:
                        self.assertGreaterEqual(start,next(p.arrival for p in processes if p.pid==pid))
                        executed[pid]+=end-start
                for p in result["processes"]:
                    self.assertEqual(executed[p["pid"]],p["burst"])
                    self.assertEqual(p["turnaround"],p["completion"]-p["arrival"])
                    self.assertEqual(p["waiting"],p["turnaround"]-p["burst"])
                    self.assertGreaterEqual(p["waiting"],0)
                    self.assertGreaterEqual(p["response"],0)

    def test_every_legacy_cli_exits_on_zero_count_without_import_dependencies(self):
        mapping=json.loads((ROOT/"tests/entrypoints.json").read_text())
        for path in mapping:
            result=subprocess.run([sys.executable,str(ROOT/path)],input="0\n",capture_output=True,text=True,timeout=2,cwd=ROOT.parent)
            self.assertEqual(result.returncode,1,path+result.stderr)
            self.assertIn("Process count",result.stderr)

    def test_original_zero_quantum_regression_exits_promptly(self):
        for path in ["Final/rr.py","Final/same_python_file/round_robin.py","Mahbub Sir/4 Round Robin.py"]:
            result=subprocess.run([sys.executable,str(ROOT/path)],input="1\n0\n1\n0\n",capture_output=True,text=True,timeout=2)
            self.assertEqual(result.returncode,1)
            self.assertIn("Invalid workload",result.stderr)

    def test_every_legacy_cli_runs_a_valid_workload(self):
        mapping=json.loads((ROOT/"tests/entrypoints.json").read_text())
        for path,algorithm in mapping.items():
            text="1\n0\n1\n" + ("1\n" if algorithm=="rr" or algorithm.startswith("priority") else "")
            result=subprocess.run([sys.executable,str(ROOT/path)],input=text,capture_output=True,text=True,timeout=2,cwd=ROOT.parent)
            self.assertEqual(result.returncode,0,path+result.stderr)
            self.assertIn("0 -> 1: P1",result.stdout)

    def test_updated_notebook_code_cells_execute_without_input(self):
        for path in (ROOT/"Mahbub Sir").glob("*.ipynb"):
            notebook=json.loads(path.read_text(encoding="utf-8"))
            scope={}
            with patch("builtins.input",side_effect=AssertionError("Unexpected prompt")),contextlib.redirect_stdout(io.StringIO()):
                for cell in notebook["cells"]:
                    if cell["cell_type"]=="code": exec(compile("".join(cell["source"]),str(path),"exec"),scope)
            self.assertEqual(len(scope["result"]["processes"]),3)


if __name__=="__main__": unittest.main()
