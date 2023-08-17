import logging
import os
import subprocess
import sys
import time
import traceback

module_logger = logging.getLogger(__name__)


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_red(message):
    print(Color.RED + message + Color.END)


def print_blue(message):
    print(Color.BLUE + message + Color.END)


def get_test_files(testpath):
    if os.path.isfile(testpath):
        return [testpath]
    else:
        res = []
        for root, dirs, files in os.walk(testpath):
            module_logger.debug("Searching %s for files ending in 'tests.py'", root)
            res.extend([os.path.join(root, file) for file in files if file.endswith("tests.py")])
        return res


def retry(fn, num_attempts=3):
    if num_attempts <= 0:
        raise Exception("Illegal num_attempts: {}".format(num_attempts))
    count = 0
    for _ in range(0, num_attempts):
        try:
            return fn()
        except Exception:
            count += 1
            print("Execution failed on attempt {} out of {}".format(count, num_attempts))
            print("Exception trace:")
            traceback.print_exc()
            if count == num_attempts:
                print("Execution failed after {} attempts".format(count))
                raise


def _run_command(
    commands,
    cwd=None,
    stderr=subprocess.STDOUT,
    shell=False,
    env=None,
    stream_stdout=True,
    throw_on_retcode=True,
    logger=None,
):
    if logger is None:
        logger = module_logger

    if cwd is None:
        cwd = os.getcwd()

    t0 = time.perf_counter()
    try:
        logger.debug("Executing {0} in {1}".format(commands, cwd))
        out = ""
        p = subprocess.Popen(commands, stdout=subprocess.PIPE, stderr=stderr, cwd=cwd, shell=shell, env=env)
        for line in p.stdout:
            line = line.decode("utf-8").rstrip()
            if line and line.strip():
                logger.debug(line)
                if stream_stdout:
                    sys.stdout.write(line)
                    sys.stdout.write("\n")
                out += line
                out += "\n"
        p.communicate()
        retcode = p.poll()
        if throw_on_retcode:
            if retcode:
                raise subprocess.CalledProcessError(retcode, p.args, output=out, stderr=p.stderr)
        return retcode, out
    finally:
        t1 = time.perf_counter()
        logger.debug("Execution took {0}s for {1} in {2}".format(t1 - t0, commands, cwd))


def run_command(
    commands, cwd=None, stderr=subprocess.STDOUT, shell=False, stream_stdout=True, throw_on_retcode=True, logger=None
):
    _, out = _run_command(
        commands,
        cwd=cwd,
        stderr=stderr,
        shell=shell,
        stream_stdout=stream_stdout,
        throw_on_retcode=throw_on_retcode,
        logger=logger,
    )
    return out
