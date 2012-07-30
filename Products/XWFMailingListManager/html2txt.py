# coding=utf-8
import re
from HTMLParser import HTMLParser

class HTMLConverter(HTMLParser):
    '''Convert HTML to plain text
    
    This class, which extends the standard HTMLParser, converts HTML to
    plain text. It does this by getting all the data in the HTML 
    elements, simplifying the whitespace, and then removing duplicate
    newlines. In addition it puts the value of the ``href`` attributes
    of the anchor elements in angle-brackets after the anchor-text.'''
    
    dupeNewlineRE = re.compile('\n\n+')
    # See Ticket 596 <https://projects.iopen.net/groupserver/ticket/596>
    def __init__(self):
        HTMLParser.__init__(self)
        self.outText = u''
        self.lastHREF = []
        self.lastData = u''

    def __unicode__(self):
        retval = self.dupeNewlineRE.sub('\n\n', self.outText)
        return retval

    def __str__(self):
        return unicode(self).encode('ascii', 'ignore')
    
    def handle_starttag(self, tag, attrs):
        # Remember the href attribute of the anchor, because it will
        #   be displayed *after* the data. The attribute may not be
        #   set because some crack smoking madman may have added anchor
        #   *targets* to the message.
        if tag == 'a':
            attrsDict = dict(attrs)
            self.lastHREF.append(attrsDict.get('href', ''))
    
    def handle_endtag(self, tag):
        # Display the value of the href attribute of the anchor, if set. 
        #   Do not display the attribute value if it is the same as the
        #   link-text.
        if tag == 'a' and self.lastHREF:
            href = self.lastHREF.pop()
            if href and (href != self.lastData):
                self.outText = self.outText + ' <%s> ' % href
        
    def handle_data(self, data):
        data = unicode(data, 'utf-8', 'ignore')
        d = data.strip()
        d = d and ('%s ' % d) or '\n'
        self.lastData = d
        self.outText = self.outText + d

def convert_to_txt(html):
    assert html, 'html argument not set.'
    converter = HTMLConverter()

    converter.feed(html)
    converter.close()

    retval = unicode(converter)
    return retval

