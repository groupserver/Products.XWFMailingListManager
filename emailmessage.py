import re
import md5
import string
from email import Parser, Header
from zope.app.datetimeutils import parseDatetimetz
from rfc822 import AddressList, parsedate_tz, mktime_tz
import zope.interface

def convert_int2b(num, alphabet, converted=[]):
    mod = num % len(alphabet); rem = num / len(alphabet)
    converted.append(alphabet[mod])
    if rem:
        return convert_int2b(rem, alphabet, converted)
    converted.reverse()

    return ''.join(converted)

def convert_int2b62(num):
    alphabet = string.printable[:62]
    
    return convert_int2b(num, alphabet, [])

def parse_disposition(s):
    matchObj = re.search('(?i)filename="*(?P<filename>[^"]*)"*', s)
    name = ''
    if matchObj:
        name = matchObj.group('filename')
    return name

def strip_subject(subject, list_title, remove_re=True):
    """ A helper function for tidying the subject line.

    """
    # remove the list title from the subject
    subject = re.sub('\[%s\]' % re.escape(list_title), '', subject).strip()
    
    # compress up the whitespace into a single space
    subject = re.sub('\s+', ' ', subject).strip()
    
    # remove the "re:" from the subject line. There are probably other variants
    # we don't yet handle.
    if subject.lower().find('re:', 0, 3) == 0 and len(subject) > 3:
        subject = subject[3:].strip()
    elif len(subject) == 0:
        subject = 'No Subject'
    
    return subject

def compress_subject(subject):
    """ Compress subject, subject.
        
    """
    return re.sub('\s+', '', subject)

def calculate_file_id(file_body, mime_type):
    length = len(file_body)
    
    md5_sum = md5.new()
    for c in file_body:
        md5_sum.update(c)
    
    file_md5 = md5_sum.hexdigest()
    
    md5_sum.update(':'+str(length)+':'+mime_type)

    return (unicode(convert_int2b62(long(md5_sum.hexdigest(), 16))), length, file_md5)

class IRDBStorageForEmailMessage(zope.interface.Interface):
    pass

class RDBEmailMessageStorage(object): 
    zope.interface.implements(IRDBStorageForEmailMessage)
    def __init__(self, email_message):
        self.email_message = email_message

    def hello_world(self):
        return 'hello'

class IEmailMessage(zope.interface.Interface):
    encoding = zope.interface.Attribute("The encoding of the email and headers.")
    attachments = zope.interface.Attribute("A list of attachment payloads, each structured "
                                            "as a dictionary, from the email (both body and "
                                            "attachments).")
    body = zope.interface.Attribute("The plain text body of the email message.")
    subject = zope.interface.Attribute("Get the subject of the email message, stripped of "
                                        "additional details (such as re:, and list title)")
    compressedSubject = zope.interface.Attribute("Get the compressed subject of the email "
                                                  "message, with all whitespace removed.")
    
    post_id = zope.interface.Attribute("The unique ID for the post, based on attributes of the message")
    topic_id = zope.interface.Attribute("The unique ID for the topic, based on attributes of the message")
    
    def get(name, default):
        """ Get the value of a header, changed to unicode using the
            encoding of the email.
            
        """

class EmailMessage(object):
    zope.interface.implements(IEmailMessage)

    def __init__(self, message, list_title='', group_id='', site_id=''):
        parser = Parser.Parser()
        msg = parser.parsestr(message)
        
        self.message = msg
        self._list_title = list_title
        self.group_id = group_id
        self.site_id = site_id
        
    def get(self, name, default=''):
        value = self.message.get(name, default)
        value, encoding = Header.decode_header(value)[0]
        
        value = unicode(value, encoding or self.encoding, 'ignore')
        
        return value
    
    @property
    def encoding(self):
        return self.message.get_param('charset', 'ascii')

    @property
    def attachments(self):
        payload = self.message.get_payload()
        if isinstance(payload, list):
            outmessages = []
            out = []
            for i in payload:
                if i.is_multipart():
                    for b in i.get_payload():
                        outmessages.append(b)
                else:
                    outmessages.append(i)
                    
            for msg in outmessages:
                actual_payload = msg.get_payload(decode=True)
                filename = unicode(parse_disposition(msg.get('content-disposition', '')), 
                                    self.encoding, 'ignore')
                fileid, length, md5_sum = calculate_file_id(actual_payload, msg.get_content_type())
                out.append({'payload': actual_payload, 
                             'fileid': fileid, 
                             'filename': filename, 
                             'length': length, 
                             'md5': md5_sum, 
                             'charset': msg.get_charset(), 
                             'maintype': msg.get_content_maintype(), 
                             'subtype': msg.get_content_subtype(), 
                             'mimetype': msg.get_content_type(), 
                             'contentid': msg.get('content-id', '')})
            return out
        else:
            # since we aren't a bunch of attachments, actually decode the body
            payload = self.message.get_payload(decode=True)
            
        filename = unicode(parse_disposition(self.message.get('content-disposition', '')), 
                            self.encoding, 'ignore')
        
        fileid, length, md5_sum = calculate_file_id(payload, self.message.get_content_type())
        return [ {'payload': payload, 
                  'md5': md5_sum, 
                  'fileid': fileid, 
                  'filename': filename, 
                  'length': length, 
                  'charset': self.message.get_charset(), 
                  'maintype': self.message.get_content_maintype(), 
                  'subtype': self.message.get_content_subtype(), 
                  'mimetype': self.message.get_content_type(), 
                  'contentid': self.message.get('content-id', '')}
               ]

    @property
    def headers(self):
        # return a flattened version of the headers
        header_string = '\n'.join(map(lambda x: '%s: %s' % (x[0], x[1]), self.message._headers))
        return unicode(header_string, self.encoding, 'ignore')

    @property
    def body(self):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] != 'html':
                return unicode(item['payload'], self.encoding, 'ignore')
        return ''

    @property
    def htmlbody(self):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] == 'html':
                return unicode(item['payload'], self.encoding, 'ignore')
        return ''

    @property
    def subject(self):
        return strip_subject(self.get('subject'), self._list_title)

    @property
    def compressedSubject(self):
        return compress_subject(self.subject)

    @property
    def sender(self):
        sender = self.get('from')
        
        if sender:
            name, sender = AddressList(sender)[0]
        
        return sender

    @property
    def to(self):
        to = self.get('to')
        
        if to:
            name, to = AddressList(to)[0]
        
        return to

    @property
    def title(self):
        return '%s / %s' % (self.subject, self.sender)

    @property
    def inreplyto(self):
        return self.get('in-reply-to')

    @property
    def date(self):
        return parseDatetimetz(self.get('date'))
    
    @property
    def md5body(self):
        return md5.new(self.body).hexdigest()
    
    @property
    def topic_id(self):
        # this is calculated from what we have/know
        tid = md5.new(self.subject+':'+self.group_id+':'+self.site_id).hexdigest()
        
        return unicode(convert_int2b62(long(tid, 16)))
        
    @property
    def post_id(self):
        # this is calculated from what we have/know
        len_payloads = sum([ x['length'] for x in self.attachments ])
        pid = md5.new(self.topic_id+':'+self.get('subject')+':'+self.md5body+':'+self.sender+':'+
                       self.inreplyto+':'+str(len_payloads)).hexdigest()
        return unicode(convert_int2b62(long(pid, 16)))
        
