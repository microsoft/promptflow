import logging
import sys


class _LoggerFactory:
    @staticmethod
    def get_logger(name="promptflow-cli", verbosity=logging.INFO, target_stdout=False):
        logger = logging.getLogger(name)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        if not _LoggerFactory._find_handler(logger, logging.StreamHandler):
            _LoggerFactory._add_handler(logger, verbosity, target_stdout)
        return logger

    @staticmethod
    def _find_handler(logger, handler_type):
        for log_handler in logger.handlers:
            if isinstance(log_handler, handler_type):
                return log_handler
        return None

    @staticmethod
    def _add_handler(logger, verbosity, target_stdout=False):
        # set target_stdout=True can log data into sys.stdout instead of default sys.stderr, in this way
        # logger info and python print result can be synchronized
        handler = logging.StreamHandler(stream=sys.stdout) if target_stdout else logging.StreamHandler()
        # formatter = logging.Formatter(
        #     "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
        # )
        formatter = logging.Formatter("[%(name)s][%(levelname)s] - %(message)s")
        handler.setFormatter(formatter)
        handler.setLevel(verbosity)
        logger.addHandler(handler)
