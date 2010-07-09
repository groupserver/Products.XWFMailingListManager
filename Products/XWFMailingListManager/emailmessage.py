# coding=utf-8
try:
    from hashlib import md5
except:
    from md5 import md5
import re, string, datetime, time, codecs
from rfc822 import AddressList
import sqlalchemy as sa
from sqlalchemy.exceptions import SQLError
from zope.interface import Interface, Attribute, implements
from zope.datetime import parseDatetimetz
from Products.XWFCore.XWFUtils import removePathsFromFilenames
from MailBoxerTools import convertHTML2Text
from email import Parser, Header
from addapost import tagProcess
from crop_email import crop_email
import stopwords

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

reRegexp = re.compile('re:', re.IGNORECASE)
fwRegexp = re.compile('fw:', re.IGNORECASE)
fwdRegexp = re.compile('fwd:', re.IGNORECASE)
# See <http://www.w3.org/TR/unicode-xml/#Suitable>
uParaRegexep = re.compile(u'[\u2028\u2029]+')
annoyingChars = string.whitespace + u'\uFFF9\uFFFA\uFFFB\uFFFC\uFEFF'
annoyingCharsL = annoyingChars + u'\u202A\u202D'
annoyingCharsR = annoyingChars + u'\u202B\u202E'
def strip_subject(subject, list_title, remove_re=True):
    """ A helper function for tidying the subject line.

    """
    # remove the list title from the subject, if it isn't just an empty string
    if list_title:
        subject = re.sub('\[%s\]' % re.escape(list_title), '', subject).strip()
    
    subject = uParaRegexep.sub(u' ', subject)
    # compress up the whitespace into a single space
    subject = re.sub('\s+', ' ', subject).strip()
    if remove_re:
        # remove the "re:" from the subject line. There are probably other variants
        # we don't yet handle.
        subject = reRegexp.sub('', subject)
        subject = fwRegexp.sub('', subject)
        subject = fwdRegexp.sub('', subject)
        subject = subject.lstrip(annoyingCharsL +'[')
        subject = subject.rstrip(annoyingCharsR +']')
    else:
        subject = subject.lstrip(annoyingCharsL)
        subject = subject.rstrip(annoyingCharsR)
    if len(subject) == 0:
        subject = 'No Subject'
    return subject

def normalise_subject(subject):
    """ Compress whitespace and lower-case subject 
        
    """
    return re.sub('\s+', '', subject).lower()

def calculate_file_id(file_body, mime_type):
    #
    # Two files will have the same ID if
    # - They have the same MD5 Sum, and
    # - They have the same length, and
    # - They have the same MIME-type.
    #
    length = len(file_body)
    
    md5_sum = md5.new()
    for c in file_body:
        md5_sum.update(c)
    
    file_md5 = md5_sum.hexdigest()
    
    md5_sum.update(':'+str(length)+':'+mime_type)

    return (unicode(convert_int2b62(long(md5_sum.hexdigest(), 16))), length, file_md5)

class IRDBStorageForEmailMessage(Interface):
    pass

class RDBFileMetadataStorage(object):
    def __init__(self, context, email_message, file_ids):
        self.context = context
        self.email_message = email_message
        self.file_ids = file_ids
    
    def set_zalchemy_adaptor(self, da):
        self.fileTable = da.createTable('file')
        self.postTable = da.createTable('post')
        
    def insert(self):
        # FIXME: references like this should *NOT* be hardcoded!
        storage = self.context.FileLibrary2.get_fileStorage()
        for fid in self.file_ids:
            # for each file, get the metadata and insert it into our RDB table
            attachedFile = storage.get_file(fid)
            i = self.fileTable.insert()
            title = attachedFile.getProperty('title','')
            i.execute(file_id=fid,
                      mime_type=attachedFile.getProperty('content_type',''),
                      file_name=attachedFile.getProperty('title',''),
                      file_size=getattr(attachedFile, 'size', 0),
                      date=self.email_message.date,
                      post_id=self.email_message.post_id,
                      topic_id=self.email_message.topic_id)

        # set the flag on the post table to avoid lookups
        self.postTable.update(self.postTable.c.post_id == self.email_message.post_id
                                   ).execute(has_attachments=True)

class RDBEmailMessageStorage(object): 
    implements(IRDBStorageForEmailMessage)
    
    def __init__(self, email_message):
        self.email_message = email_message

    def set_zalchemy_adaptor(self, da):
        self.postTable = da.createTable('post')
        self.topicTable = da.createTable('topic')
        self.topic_word_countTable = da.createTable('topic_word_count')
        self.post_tagTable = da.createTable('post_tag')
        self.post_id_mapTable = da.createTable('post_id_map')

    def _get_topic(self):
        and_ = sa.and_
        
        r = self.topicTable.select(and_(self.topicTable.c.topic_id == self.email_message.topic_id, 
                                        self.topicTable.c.group_id == self.email_message.group_id, 
                                        self.topicTable.c.site_id == self.email_message.site_id)).execute()
        
        return r.fetchone()

    def insert(self):
        and_ = sa.and_

        #
        # add the post itself
        #
        i = self.postTable.insert()
        i.execute(post_id=self.email_message.post_id, 
                   topic_id=self.email_message.topic_id, 
                   group_id=self.email_message.group_id, 
                   site_id=self.email_message.site_id, 
                   user_id=self.email_message.sender_id, 
                   in_reply_to=self.email_message.inreplyto, 
                   subject=self.email_message.subject, 
                   date=self.email_message.date, 
                   body=self.email_message.body, 
                   htmlbody=self.email_message.html_body, 
                   header=self.email_message.headers, 
                   has_attachments=bool(self.email_message.attachment_count))
        #
        # add/update the topic
        #
        topic = self._get_topic()
        if not topic:
            i = self.topicTable.insert()
            i.execute(topic_id=self.email_message.topic_id, 
                       group_id=self.email_message.group_id, 
                       site_id=self.email_message.site_id, 
                       original_subject=self.email_message.subject, 
                       first_post_id=self.email_message.post_id, 
                       last_post_id=self.email_message.post_id, 
                       last_post_date=self.email_message.date, 
                       num_posts=1)
        else:
            num_posts = topic['num_posts']
            if (time.mktime(topic['last_post_date'].timetuple()) > 
                time.mktime(self.email_message.date.timetuple())):
                last_post_date = topic['last_post_date']
                last_post_id = topic['last_post_id']
            else:
                last_post_date = self.email_message.date
                last_post_id = self.email_message.post_id
                
            self.topicTable.update(and_(self.topicTable.c.topic_id == self.email_message.topic_id, 
                                         self.topicTable.c.group_id == self.email_message.group_id, 
                                         self.topicTable.c.site_id == self.email_message.site_id)
                                   ).execute(num_posts=num_posts+1, 
                                             last_post_id=last_post_id, 
                                             last_post_date=last_post_date)
        #
        # add any tags we have for the post
        #
        i = self.post_tagTable.insert()
        for tag in self.email_message.tags:
            i.execute(post_id=self.email_message.post_id,
                      tag=tag)

    def insert_legacy_id(self):
        #
        # This is only really needed when doing an upgrade run prior to GS 1.0
        #
        i = self.post_id_mapTable.insert()
        gs_original_id = self.email_message.get('x-gsoriginal-id', None)
        if gs_original_id:
            i.execute(old_post_id=gs_original_id,
                      new_post_id=self.email_message.post_id)

    def insert_keyword_count( self ):
        and_ = sa.and_
        #    
        # add/update the word count for the topic
        #
        counts = self.email_message.word_count
        for word in counts:
            # determine if the word exists before inserting or updating. It, despite appearances, is was actually
            # significantly faster in a real-world trial to do it this way (at least 20% faster).
            try:
                i = self.topic_word_countTable.insert()
                i.execute(topic_id=self.email_message.topic_id, 
                           word=word, 
                           count=counts[word])
            except SQLError:
                # otherwise select and update
                r = self.topic_word_countTable.select(and_(self.topic_word_countTable.c.topic_id == self.email_message.topic_id, 
                                                           self.topic_word_countTable.c.word == word)).execute().fetchone() 
                if r:
                    self.topic_word_countTable.update(and_(self.topic_word_countTable.c.topic_id == self.email_message.topic_id, 
                                                           self.topic_word_countTable.c.word == word)).execute(count=r['count']+counts[word])
                           
    def remove(self):
        topic = self._get_topic()
        if topic['num_posts'] == 1:
            self.topicTable.delete(self.topicTable.c.topic_id == self.email_message.topic_id).execute()         

        #self.topicTable.update( self.topicTable.c.first_post_id == self.email_message.post_id ).execute( first_post_id='' )
        #self.topicTable.update( self.topicTable.c.last_post_id == self.email_message.post_id ).execute( last_post_id='' )
        self.postTable.delete(self.postTable.c.post_id == self.email_message.post_id).execute()    

class IEmailMessage(Interface):
    """ A representation of an email message.
    
    """
    post_id = Attribute("The unique ID for the post, based on attributes of the message")
    topic_id = Attribute("The unique ID for the topic, based on attributes of the message")
    
    encoding = Attribute("The encoding of the email and headers.")
    attachments = Attribute("A list of attachment payloads, each structured "
                            "as a dictionary, from the email (both body and "
                            "attachments).")
    body = Attribute("The plain text body of the email message.")
    html_body = Attribute("The html body of the email message, if one exists")
    subject = Attribute("Get the subject of the email message, stripped of "
                        "additional details (such as re:, and list title)")
    compressed_subject = Attribute("Get the compressed subject of the email "
                                  "message, with all whitespace removed.")
    
    sender_id = Attribute("The user ID of the message sender")
    headers = Attribute("A flattened version of the email headers")
    language = Attribute("The language in which the email has been composed")
    inreplyto = Attribute("The value of the inreplyto header if it exists")
    date = Attribute("The date on which the email was sent")
    md5_body = Attribute("An md5 checksum of the plain text body of the email")
    
    to = Attribute("The email address the message was sent to")
    sender = Attribute("The email address the message was sent from")
    name = Attribute("The name of the sender, from the header. This is not "
                     "related to their name as set in GroupServer")
    title = Attribute("An attempt at a title for the email")
    tags = Attribute("A list of tags that describe the email")
    
    attachment_count = Attribute("A count of attachments which have a filename")
    word_count = Attribute("A dictionary of words and their count within the document")
    
    def get(name, default): #@NoSelf
        """ Get the value of a header, changed to unicode using the
            encoding of the email.
        
        @param name: identifier of header, eg. 'subject'
        @param default: default value, if header does not exist. Defaults to '' if
            left unspecified
        """

def check_encoding(encoding):
    # a slightly wierd encoding that isn't in the standard encoding table
    if encoding.lower() == 'macintosh':
        encoding = 'mac_roman'
        
    try:
        codecs.lookup(encoding)
    except:
        # play it pretty safe ... we're going to be ignoring errors in
        # the encoding anyway, and UTF-8 is going to be right more of the time
        # in the very, very rare case that we have to force this!
        encoding = 'utf-8'
    
    return encoding

class EmailMessage(object):
    implements(IEmailMessage)

    def __init__(self, message, list_title='', group_id='', site_id='', sender_id_cb=None,
                       replace_mail_date=True):
        parser = Parser.Parser()
        msg = parser.parsestr(message)
        
        self.message = msg
        self._list_title = list_title
        self.group_id = group_id
        self.site_id = site_id
        self.sender_id_cb = sender_id_cb
        self.replace_mail_date = replace_mail_date
        self._date = datetime.datetime.now()

        self.__body = None
        self.__attachments = None
        self.__subject = None
        
    def get(self, name, default=''):
        value = self.message.get(name, default)
        header_parts = []
        for value, encoding in Header.decode_header(value):
            encoding = encoding and check_encoding(encoding) or self.encoding
            header_parts.append(unicode(value, encoding, 'ignore'))
        
        return u' '.join(header_parts)

    @property
    def sender_id(self):
        if self.sender_id_cb:
            return self.sender_id_cb( self.sender )
        
        return ''
    
    @property
    def encoding(self):
        encoding = check_encoding(self.message.get_param('charset', 'utf-8'))
        
        return encoding

    @property
    def attachments(self):
        def split_multipart(msg, pl):
            if msg.is_multipart():
                for b in msg.get_payload():
                    pl = split_multipart(b, pl)
            else:
                pl.append(msg)
            
            return pl           

        if self.__attachments == None:
            payload = self.message.get_payload()
            if isinstance(payload, list):
                outmessages = []
                self.__attachments = []
                for i in payload:
                    outmessages = split_multipart(i, outmessages)
                        
                for msg in outmessages:
                    actual_payload = msg.get_payload(decode=True)
                    encoding = msg.get_param('charset', self.encoding)
                    filename = unicode(parse_disposition(msg.get('content-disposition', '')), 
                                       encoding, 'ignore')
                    fileid, length, md5_sum = calculate_file_id(actual_payload, msg.get_content_type())
                    self.__attachments.append({
                          'payload': actual_payload, 
                          'fileid': fileid, 
                          'filename': filename, 
                          'length': length, 
                          'md5': md5_sum, 
                          'charset': encoding, # --=mpj17=-- Issues?
                          'maintype': msg.get_content_maintype(), 
                          'subtype': msg.get_content_subtype(), 
                          'mimetype': msg.get_content_type(), 
                          'contentid': msg.get('content-id', '')})
                
            else:
                # since we aren't a bunch of attachments, actually decode the body
                payload = self.message.get_payload(decode=True)
                
                filename = unicode(parse_disposition(self.message.get('content-disposition', '')), 
                                    self.encoding, 'ignore')
                
                fileid, length, md5_sum = calculate_file_id(payload, self.message.get_content_type())
                self.__attachments = [ {
                          'payload': payload, 
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
        assert self.__attachments != None
        assert type(self.__attachments) == list
        return self.__attachments

    @property
    def headers(self):
        # return a flattened version of the headers
        header_string = '\n'.join(map(lambda x: '%s: %s' % (x[0], x[1]), self.message._headers))
        
        if not isinstance(header_string, unicode):
            header_string = unicode(header_string, self.encoding, 'ignore')
        
        return header_string

    @property
    def attachment_count(self):
        count = 0
        for item in self.attachments:
            if item['filename']:
                count += 1
        
        return count

    @property
    def language(self):
        # one day we might want to detect languages, primarily this
        # will be used for stemming, stopwords and search
        return 'en'
    
    @property
    def word_count(self):
        wc = {}
        cropped_body, rest = crop_email(self.body) #@UnusedVariable
        process_body = ''
        for line in cropped_body.split('\n'):
            if line and line[0] != '>':
                process_body += line+'\n'

        for word in process_body.split():
            word = word.lower()
            subs = (("'s$",""), ("\.$",""), (",$",""),("'$",""))
            for repstr, substr in subs:
                word = re.sub(repstr, substr, word)
            
            # check for stopwords
            if word in stopwords.en:
                continue
            
            skip = False
            for letter in word:
                if letter not in string.ascii_lowercase+string.digits:
                    skip = True
                    break

            if skip:
                continue
            
            if wc.has_key(word):
                wc[word] += 1
            else:
                wc[word] = 1
        
        return wc

    @property
    def body(self):
        if self.__body == None:
            self.__body = u''
            for item in self.attachments:
                if item['filename'] == '' and item['subtype'] != 'html':
                    retval = item
                    self.__body = unicode(item['payload'], self.encoding, 'ignore')
                    break
            html_body = self.html_body
            if html_body and (not self.__body):
                plain_body = convertHTML2Text(html_body.encode(self.encoding,
                                                        'xmlcharrefreplace'))
                self.__body = unicode(plain_body, self.encoding, 'ignore')

        assert self.__body != None
        assert type(self.__body) == unicode
        return self.__body

    @property
    def html_body(self):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] == 'html':
                return unicode(item['payload'], self.encoding, 'ignore')
        return ''

    @property
    def subject(self):
        if self.__subject == None:
            self.__subject = strip_subject(self.get('subject'), self._list_title)
        return self.__subject

    @property
    def compressed_subject(self):
        return normalise_subject(self.subject)

    @property
    def sender(self):
        sender = self.get('from')
        
        if sender:
            name, sender = AddressList(sender)[0] #@UnusedVariable
            sender = sender.lower()
        
        return sender

    @property
    def name(self):
        sender = self.get('from')
        name = ''
        
        if sender:
            name, sender = AddressList(sender)[0]
        
        return name

    @property
    def to(self):
        to = self.get('to')
        
        if to:
            name, to = AddressList(to)[0] #@UnusedVariable
            to = to.lower()
        # --=mpj17=-- TODO: Add the group name.
        return to

    @property
    def title(self):
        return '%s / %s' % (self.subject, self.sender)

    @property
    def inreplyto(self):
        return self.get('in-reply-to')

    @property
    def date(self):
        if self.replace_mail_date:
            return self._date
        
        d = self.get('date', '').strip()
        if d:
            # if we have the format Sat, 10 Mar 2007 22:47:20 +1300 (NZDT)
            # strip the (NZDT) bit before parsing, otherwise we break the parser
            d = re.sub(' \(.*?\)','', d)
            return parseDatetimetz(d)
        
        return self._date

    @property
    def md5_body(self):
        return md5.new(self.body.encode('utf-8')).hexdigest()
    
    @property
    def topic_id(self):
        # this is calculated from what we have/know
        
        # A topic_id for two posts will clash if
        #   - The compressedsubject, group ID and site ID are all identical
        items = self.compressed_subject + ':' + self.group_id + ':' + self.site_id
        tid = md5.new(items.encode('utf-8')).hexdigest()
        
        return unicode(convert_int2b62(long(tid, 16)))
    
    @property
    def tags( self ):
        keywords = self.get( 'keywords', '' )
        if not keywords:
            keywords = self.get('x-keywords', '')
        
        if keywords:   
            return tagProcess( keywords )
        
        return []
        
    @property
    def post_id(self):
        # this is calculated from what we have/know
        len_payloads = sum([ x['length'] for x in self.attachments ])
        
        # A post_id for two posts will clash if
        #    - The topic IDs are the same, and
        #    - The subject is the same (this may not be the same as 
        #      compressed subject used in topic id)
        #    - The body of the posts are the same, and
        #    - The posts are from the same author, and
        #    - The posts respond to the same message, and
        #    - The posts have the same length of attachments.
        items = (self.topic_id + ':' + self.subject + ':' +
                  self.md5_body + ':' + self.sender + ':' + 
                  self.inreplyto + ':' + str(len_payloads))
        pid = md5.new(items.encode('utf-8')).hexdigest()
        
        return unicode(convert_int2b62(long(pid, 16)))
