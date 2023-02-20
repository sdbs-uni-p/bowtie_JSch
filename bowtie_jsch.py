#!/usr/bin/env python3
from classes import *
from dataclasses import dataclass
from importlib import metadata
import io
import json
import sys
import traceback

@dataclass
class Runner:
    _started: bool = False
    _stdout: io.TextIOWrapper = sys.stdout


    def run(self, stdin=sys.stdin):
        for line in stdin:
            each = json.loads(line)
            cmd = each.pop("cmd")
            response = getattr(self, f"cmd_{cmd}")(**each)
            self._stdout.write(f"{json.dumps(response)}\n")
            self._stdout.flush()


    def cmd_start(self, version):
        assert version == 1
        self._started = True
        return dict(
            ready=True,
            version=1,
            implementation=dict(
                language="python",
                name="jsch",
                version="1.0",
                homepage="https://jreutter.sitios.ing.uc.cl/JSch/",
                issues=(
                    "unknow"
                ),
                dialects=[
                    "http://json-schema.org/draft-07/schema#",
                    "http://json-schema.org/draft-06/schema#",
                    "http://json-schema.org/draft-04/schema#",
                    "http://json-schema.org/draft-03/schema#",
                    "https://json-schema.org/draft/2020-12/schema",
                ],
            ),
        )


    def cmd_dialect(self, dialect):
        assert self._started, "Not started!"
        return dict(ok=False)


    def cmd_run(self, case, seq):
        assert self._started, "Not started!"
        schema = case["schema"]
        schemas_schema = get_schema(schema)
        results = []
        for test in case["tests"]:
            result = schemas_schema.validate(test["instance"])
            results.append({"valid": result.is_valid})

        return dict(seq=seq, results=results)

    def cmd_stop(self):
        assert self._started, "Not started!"
        sys.exit(0)


Runner().run()
