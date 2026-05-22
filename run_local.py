import subprocess
import sys


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    python = sys.executable

    run([python, "manage.py", "migrate"])
    run([python, "manage.py", "seed_week"])
    run([python, "manage.py", "runserver", "127.0.0.1:8010"])


if __name__ == "__main__":
    main()
