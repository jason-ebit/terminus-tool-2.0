# T4 practice tasks

Three small Python repair tasks: discount-boundary (easy), stable-dedup (easy), merge-intervals (medium). Each ZIP contains a single task folder.

```text
task-name/
  instruction.md
  task.toml
  README.md
  environment/
    Dockerfile
    app.py
  solution/
    solve.sh
  tests/
    Dockerfile
    test.sh
    test_outputs.py
```

In Ubuntu/WSL with Docker running and Harbor installed, run from this folder (zip a task folder first if you want to upload it to the checker site):

```bash
harbor run --agent oracle --path ./discount-boundary
harbor run --agent oracle --path ./stable-dedup
harbor run --agent oracle --path ./merge-intervals
```

These use the local Terminal-Bench T4 layout: task.toml, 28800-second agent timeout, canary, separate verifier and explicit artifact transfer. Python package versions follow that clone's checks. All three final tasks were built and run with Harbor on Ubuntu/Docker: oracle reward 1.0 and NOP reward 0.0, with no trial exceptions in the successful runs. Direct Python checks also rejected twelve wrong implementations. Detailed logs are in the separate review evidence bundle.

For the checker website, explicitly select T4 preview before uploading each ZIP. A T3 failure for a T4 canary/timeout is expected. The tasks are internal examples with disclosed placeholder metadata and AI-assisted README text, not ready for official submission. They intentionally have no fake evaluation trajectories or professional-experience claims.

The final checker runs passed 22/22 static gates for every ZIP. Scores 96/95/97 are model-assisted comparison figures, not acceptance. These deliberately simple tasks still require review under the demanding benchmark rubric.
