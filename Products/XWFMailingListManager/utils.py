import re
try:
    from hashlib import md5
except:
    from md5 import md5

def filter_command_string(s):
    parts = filter(None, map(lambda x: re.sub('\W', '', x), s.split()))
    
    return ' '.join(parts)

def check_for_commands(msg, commands):
    if not isinstance(commands, list) and not isinstance(commands, tuple):
        commands = (commands,)
        
    cstring = filter_command_string(msg.subject).lower()
    for command in commands:
        # command must occur either at the start of string or after a space,
        # and at the end of a string, or be followed by a space
        if re.search('( |^)%s( |$)' % command.lower(), cstring):
            return True
    
    # since that didn't work, try again with the first 100 chars of the body
    cstring = filter_command_string(msg.body[:100]).lower()
    for command in commands:
        if re.search('( |^)%s( |$)' % command.lower(), cstring):
            return True
        
    return False
    
def pin(email, hashkey):
    # returns the hex-digits for a randomized md5 of sender.
    res = md5(email.lower() + hashkey).hexdigest()
    
    return res[:8]

# mail-parameter in the smtp2http-request
MAIL_PARAMETER_NAME = "Mail"
def getMailFromRequest(REQUEST):
    # returns the Mail from the REQUEST-object as string
        
    return str(REQUEST[MAIL_PARAMETER_NAME])