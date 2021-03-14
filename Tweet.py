import pycld2 as cld
import logging

log = logging.getLogger(__name__)

# XXX make it more like a proxy for twitter.Status
class Tweet(object):
    """Wrap a twitter.Status object with language detection methods."""

    language_codes = [x[1] for x in cld.LANGUAGES]

    def __init__(self, status):
        self.status = status
        self.cld_bytes = 0
        self.cld_reliable = None
        self.cld_details = None

        try:
            # topLanguageName, topLanguageCode, isReliable, textBytesFound, details
            self.cld_reliable, self.cld_bytes, self.cld_details = cld.detect(
                status.text.encode("ascii", "ignore"), isPlainText=True
            )
        except UnicodeEncodeError as e:
            log.warn("language detection failed on %r" % status.text)

    def get_language_code(self):
        if not self.cld_details:
            return None

        return self.cld_details[0][1]
