import re
from email import Parser, Header
import zope.interface

def parse_disposition( s ):
    matchObj = re.search('(?i)filename="*(?P<filename>[^\s"]*)"*', s)
    name = ''
    if matchObj:
        name = matchObj.group('filename')
    return name

def strip_subject( subject, list_title, remove_re=True ):
    """ A helper function for tidying the subject line.

    """
    # remove the list title from the subject
    subject = re.sub('\[%s\]' % re.escape( list_title ), '', subject ).strip()
    
    # compress up the whitespace into a single space
    subject = re.sub('\s+', ' ', subject).strip()
    
    # remove the "re:" from the subject line. There are probably other variants
    # we don't yet handle.
    if subject.lower().find('re:', 0, 3) == 0 and len(subject) > 3:
        subject = subject[3:].strip()
    elif len(subject) == 0:
        subject = 'No Subject'
    
    return subject

def compress_subject( subject ):
    """ Compress subject, subject.
        
    """
    return re.sub('\s+', '', subject)

class IRDBStorageForEmailMessage( zope.interface.Interface ):
    pass

class RDBEmailMessageStorage( object ): 
    zope.interface.implements( IRDBStorageForEmailMessage )
    def __init__( self, email_message ):
        self.email_message = email_message

    def hello_world( self ):
        return 'hello'

class IEmailMessage( zope.interface.Interface ):
    encoding = zope.interface.Attribute( "The encoding of the email and headers." )
    attachments = zope.interface.Attribute( "A list of attachment payloads, each structured "
                                            "as a dictionary, from the email (both body and "
                                            "attachments)." )
    body = zope.interface.Attribute( "The plain text body of the email message." )
    subject = zope.interface.Attribute( "Get the subject of the email message, stripped of "
                                        "additional details (such as re:, and list title)" )
    compressedSubject = zope.interface.Attribute( "Get the compressed subject of the email "
                                                  "message, with all whitespace removed." )
    
    def get( name, default ):
        """ Get the value of a header, changed to unicode using the
            encoding of the email.
            
        """

class EmailMessage( object ):
    zope.interface.implements( IEmailMessage )

    def __init__( self, message, list_title='' ):
        parser = Parser.Parser()
        msg = parser.parsestr( message )
        
        self.message = msg
        self._list_title = list_title
        
    def get( self, name, default='' ):
        value = self.message.get( name, default )
        value, encoding = Header.decode_header( value )[0]
        
        value = unicode( value, encoding or self.encoding, 'ignore' )
        
        return value
    
    @property
    def encoding( self ):
        return self.message.get_param('charset', 'ascii')

    @property
    def attachments( self ):
        payload = self.message.get_payload()
        if isinstance( payload, list ):
            outmessages = []
            out = []
            for i in payload:
                if i.is_multipart():
                    for b in i.get_payload():
                        outmessages.append( b )
                else:
                    outmessages.append(i)
                    
            for msg in outmessages:
                actual_payload = msg.get_payload( decode=True )
                filename = parse_disposition( msg.get('content-disposition','') )
                out.append( {'payload': actual_payload,
                             'filename': filename,
                             'length': len(actual_payload),
                             'charset': msg.get_charset(),
                             'maintype': msg.get_content_maintype(),
                             'subtype': msg.get_content_subtype(),
                             'mimetype': msg.get_content_type()} )
            return out

        filename = parse_disposition( self.message.get('content-disposition','') )
        return [ {'payload': payload,
                  'filename': filename,
                  'length': len(payload),
                  'charset': self.message.get_charset(),
                  'maintype': self.message.get_content_maintype(),
                  'subtype': self.message.get_content_subtype(),
                  'mimetype': self.message.get_content_type()}
               ]

    @property
    def body( self ):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] != 'html':
                return unicode( item['payload'], self.encoding, 'ignore' )
        return ''

    @property
    def htmlbody( self ):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] == 'html':
                return unicode( item['payload'], self.encoding, 'ignore' )
        return ''

    @property
    def subject( self ):
        return strip_subject( self.get( 'subject' ), self._list_title )

    @property
    def compressedSubject( self ):
        return compress_subject( self.subject )
    

