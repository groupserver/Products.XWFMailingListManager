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

    def __unicode__(self):
        retval = self.dupeNewlineRE.sub('\n\n', self.outText)
        return retval

    def __str__(self):
        return unicode(self).encode('ascii', 'ignore')
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrsDict = dict(attrs)
            self.lastHREF.append(attrsDict.get('href', ''))
    
    def handle_endtag(self, tag):
        if tag == 'a' and self.lastHREF:
            href = self.lastHREF.pop()
            if href:
                self.outText = self.outText + ' <%s>' % href
        
    def handle_data(self, data):
        d = data.strip()
        d = d and d or '\n'
        self.outText = self.outText + d

def convert_to_txt(html):
    assert html, 'html argument not set.'
    converter = HTMLConverter()

    converter.feed(html)
    converter.close()

    retval = unicode(converter)
    return retval

