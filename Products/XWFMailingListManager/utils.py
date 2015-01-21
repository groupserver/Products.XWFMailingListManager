try:
    from hashlib import md5
except:
    from md5 import md5


def pin(email, hashkey):
    # returns the hex-digits for a randomized md5 of sender.
    res = md5(email.lower() + hashkey).hexdigest()

    return res[:8]


# mail-parameter in the smtp2http-request
MAIL_PARAMETER_NAME = "Mail"


def getMailFromRequest(REQUEST):
    # returns the Mail from the REQUEST-object as string

    return str(REQUEST[MAIL_PARAMETER_NAME])
