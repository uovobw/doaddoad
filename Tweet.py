import cld
import logging

log = logging.getLogger(__name__)

# XXX make it more like a proxy for twitter.Status
class Tweet(object):
    """Wrap a twitter.Status object with language detection methods."""

    language_codes = [ x[1] for x in cld.LANGUAGES ]

    def __init__(self, status):
        self.status = status
        self.cld_result = None

        try:
            # topLanguageName, topLanguageCode, isReliable, textBytesFound, details
            self.cld_result = cld.detect(status.text.encode("ascii", "ignore"),
                                         isPlainText=True,
                                         includeExtendedLanguages=False)
        except UnicodeEncodeError, e:
            log.warn("language detection failed on %r" % status.text)

    def get_language_code(self, reliable=True):
        if not self.cld_result: return None

        if reliable:
            return reliable == self.cld_result[2] and self.cld_result[1] or None

        return self.cld_result[1]



