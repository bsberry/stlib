import epyqlib.utils.qt
import logging
import sys
import twisted.internet.defer

__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


logger = logging.getLogger(__name__)


def errbackhook(error):
    epyqlib.utils.qt.exception_message_box(message=str(error))


def detour_result(result, f, *args, **kwargs):
    f(*args, **kwargs)

    return result


def logit(it):
    logger.debug('logit(): ({}) {}'.format(type(it), it))

    if isinstance(it, twisted.python.failure.Failure):
        it.printDetailedTraceback()


@twisted.internet.defer.inlineCallbacks
def retry(function, times, acceptable=None):
    if acceptable is None:
        acceptable = []

    remaining = times
    while remaining > 0:
        try:
            result = yield function()
        except Exception as e:
            if type(e) not in acceptable:
                logger.debug('green')
                raise
            logger.debug('blue')
        else:
            logger.debug('red')
            twisted.internet.defer.returnValue(result)

        remaining -= 1

    raise Exception('out of retries')


def sleep(seconds):
    d = twisted.internet.defer.Deferred()
    from twisted.internet import reactor
    reactor.callLater(seconds, d.callback, None)
    return d
