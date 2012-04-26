import logging

log = logging.Logger('strainer')

#handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(fmt)

# add formatter to ch
ch.setFormatter(formatter)

log.addHandler(ch)


__all__ = ['log']
