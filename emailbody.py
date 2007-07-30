import re, cgi, textwrap


def markup_text(messageText):
    """Mark up the plain text
    
    Used to mark up the email: the URLs are escaped, and "@"
    characters are  replaced with "( at )". 
    
    ARGUMENTS
        "messageText" The text to alter.
          
    RETURNS
        A string containing the marked-up text.
        
    SIDE EFFECTS
        None.

    NOTE    
        Originally found in XWFCore.
        
    """
    text = cgi.escape(messageText)
    text = re.sub('(?i)(http://|https://)(.+?)(\&lt;|\&gt;|\)|\]|\}|\"|\'|$|\s)', 
            '<a href="\g<1>\g<2>">\g<1>\g<2></a>\g<3>', 
            text)
    retval = text.replace('@', ' ( at ) ')
    
    return retval

def wrap_message(messageText, width=79):
    """Word-wrap the message
    
    ARGUMENTS
        "messageText" The text to alter.
        "width"       The column-number which to wrap at.
        
    RETURNS
        A string containing the wrapped text.
        
    SIDE EFFECTS
        None.
        
    NOTE
        Originally a stand-alone script in
        "Presentation/Tofu/MailingListManager/lscripts".
        
    """
    # The following expression is based on the one inside the
    #   TextWrapper class, but without the breaking on '-'.
    splitExp = (r'(\s+|(?<=[\w\!\"\'\&\.\,\?])-{2,}(?=\w))')
    t = textwrap.TextWrapper(width=width, expand_tabs=False, 
                              replace_whitespace=False, 
                              break_long_words=False)
    t.wordsep_re = re.compile(splitExp)
    retval = '\n'.join(map(lambda l: '\n'.join(t.wrap(l)), 
                            messageText.split('\n')))
    return retval

def split_message(messageText, max_consecutive_comment=12, 
  max_consecutive_whitespace=3):
    """Split the message into main body and the footer.
    
    Email messages often contain a footer at the bottom, which
    identifies the user, and who they work for. However, GroupServer
    has lovely profiles which do this, so normally we want to snip
    the footer, to reduce clutter.
    
    In addition, many users only write a short piece of text at the
    top of the email, while the remainder of the message consists
    of all the previous posts. This method also removes the
    "bottom quoting".
    
    ARGUMENTS
        "messageText" The text to process.
        "max_consecutive_comment"    The maximum number of lines
            of quoting to allow before snipping.
        "max_consecutive_whitespace" The maximum number of lines 
            that just contain whitespace to allow before snipping.
    
    RETURNS
        2-tuple, containing the strings representing the main-body
        of the message, and the footer.
    
    SIDE EFFECTS
        None.

    NOTE
        Originally a stand-alone script in
        "Presentation/Tofu/MailingListManager/lscripts".
    """
    slines = messageText.split('\n')

    intro = []; body = []; i = 1;
    bodystart = False; consecutive_comment = 0; 
    consecutive_whitespace = 0
    
    for line in slines:
        if ((line[:2] == '--') or (line[:2] == '==') 
            or (line[:2] == '__') or (line[:2] == '~~') 
            or (line [:3] == '- -')):
            bodystart = True
        
        # if we've started on the body, just append to body
        if bodystart:
            body.append(line)
        # count comments, but don't penalise top quoting as badly
        elif consecutive_comment >= max_consecutive_comment and i > 25: 
            body.append(line)
            bodystart = True
        # if we've got less than 15 lines, just put it in the intro
        elif (i <= 15):
            intro.append(line)
        elif (len(line) > 3 and line[:4] != '&gt;'):
            intro.append(line)
        elif consecutive_whitespace <= max_consecutive_whitespace:
            intro.append(line)
        else:
            body.append(line)
            bodystart = True
        
        if len(line) > 3 and (line[:4] == '&gt;' or line.lower().find('wrote:') != -1):
            consecutive_comment += 1
        else:
            consecutive_comment = 0
        
        if len(line.strip()):
            consecutive_whitespace = 0
        else:
            consecutive_whitespace += 1
        
        i += 1

    # Backtrack through the post, in reverse order
    rintro = []; trim = True
    for line in intro[::-1]:
        prevLine = intro.index(line) == 0 and '' \
                    or intro[intro.index(line)-1]
        if len(intro) < 5:
            trim = False
        if len(line) > 3:
            ls = line[:4]
        elif line.strip():
            ls = line.strip()[0]
        else:
            ls = ''
        if trim and (ls == '&gt;' or ls == ''):
            body.insert(0, line)
        elif trim and line.find('wrote:') > 2:
            body.insert(0, line)
        elif ((trim) and (len(line.strip()) > 0)
              and (len(line.strip().split()) == 1)
              and ((len(prevLine.strip()) == 0) 
                    or len(prevLine.strip().split()) == 1)):
            # IF we are trimming, and the line has non-whitepsace 
            #   characters AND there is only one word on the line,
            #   AND the previous line does NOT have any significant text
            # THEN add it to the snipped-text.
            body.insert(0, line)

        else:
            trim = False
            rintro.insert(0, line)

    # Do not snip, if we will only snip a single line of 
    #  actual content          
    if(len(body)==1):
      rintro = rintro + body
      body = []

    intro = '\n'.join(rintro)
    body = '\n'.join(body)
    retval = (intro.strip(), body)
    assert retval
    assert len(retval) == 2
    return retval

              
def get_mail_body(text):
    """Get the body of the mail message, formatted for the Web.
    
    The "self.post" instance contains the plain-text version
    of the message, as was sent out to the user's via email.
    For formatting on the Web it is necessary to convert the
    text to the correct content-type, replace all URLs with
    anchor-elements, remove all at signs, wrap the message to
    80 characters, and remove the file-notification. This method
    does these things.  
    
    ARGUMENTS
        None.
    
    RETURNS
        A string representing the formatted body of the email 
        message.
    
    SIDE EFFECTS
        None.  
    """
    # --==mpj17=-- 
    #   I have to check up with rrw to see if posts support has_key
    # assert self.post['mailBody']

    #contentType = getattr(self.post, 'content-type', None)
    #ctct = Products.XWFCore.XWFUtils.convertTextUsingContentType
    #text = ctct(body, contentType)  
    retval = ''
    if text:    
        wrappedText = wrap_message(text)
        markedUpPost = markup_text(wrappedText).strip()
        retval = markedUpPost

    #assert retval # Some messages may be blank
    return retval

def get_email_intro_and_remainder(text):
    """Get the intoduction and remainder text of the formatted post
    
    ARGUMENTS
        None.
        
    RETURNS
        A 2-tuple of the strings that represent the email intro
        and the remainder.
        
    SIDE EFFECTS
        None.
    """
    retval = split_message(get_mail_body(text))
    return retval

